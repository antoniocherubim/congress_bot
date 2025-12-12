"""
Gerenciador de sessões usando Redis como backend.
Armazena ConversationState serializado em JSON com TTL configurável.
"""
import logging
import json
from typing import Optional
from redis import Redis
from redis.exceptions import RedisError
from ..core.session_manager import ConversationState, trim_history
from ..core.models import Message, ChatTurn, Role
from ..core.registration_state import RegistrationStep, RegistrationData

logger = logging.getLogger(__name__)


class RedisSessionManager:
    """
    Gerenciador de sessões usando Redis.
    
    Armazena cada sessão em uma chave: session:{user_id}
    Com TTL configurável para expiração automática.
    """

    def __init__(
        self,
        redis_url: str,
        max_stored_turns: int = 30,
        session_ttl_seconds: int = 604800,  # 7 dias padrão
    ) -> None:
        """
        Inicializa o gerenciador de sessões Redis.
        
        Args:
            redis_url: URL de conexão Redis (ex: redis://localhost:6379/0)
            max_stored_turns: Limite de turnos armazenados (para poda)
            session_ttl_seconds: TTL em segundos para expiração de sessões
        """
        self._redis = Redis.from_url(redis_url, decode_responses=False)  # decode_responses=False para bytes
        self._max_stored_turns = max_stored_turns
        self._session_ttl_seconds = session_ttl_seconds
        
        # Testar conexão
        try:
            self._redis.ping()
            logger.info(
                f"RedisSessionManager inicializado: redis_url={redis_url}, "
                f"ttl={session_ttl_seconds}s, max_turns={max_stored_turns}"
            )
        except RedisError as e:
            logger.error(f"Erro ao conectar ao Redis: {e}")
            raise

    def _serialize_state(self, state: ConversationState) -> bytes:
        """
        Serializa ConversationState para JSON (bytes).
        
        Args:
            state: Estado da conversa
            
        Returns:
            JSON serializado como bytes
        """
        # Serializar histórico
        history_data = []
        for turn in state.history:
            history_data.append({
                "user_message": {
                    "role": turn.user_message.role.value,
                    "content": turn.user_message.content,
                },
                "assistant_message": {
                    "role": turn.assistant_message.role.value,
                    "content": turn.assistant_message.content,
                },
            })
        
        # Serializar dados de inscrição
        reg_data = state.registration_data
        registration_data_dict = {
            "full_name": reg_data.full_name,
            "email": reg_data.email,
            "cpf": reg_data.cpf,
            "phone": reg_data.phone,
            "city": reg_data.city,
            "state": reg_data.state,
            "profile": reg_data.profile,
        }
        
        # Montar dict completo
        state_dict = {
            "user_id": state.user_id,
            "history": history_data,
            "registration_step": state.registration_step.value,
            "registration_data": registration_data_dict,
            "max_stored_turns": state.max_stored_turns,
        }
        
        return json.dumps(state_dict, ensure_ascii=False).encode("utf-8")

    def _deserialize_state(self, data: bytes) -> ConversationState:
        """
        Deserializa JSON (bytes) para ConversationState.
        
        Args:
            data: JSON serializado como bytes
            
        Returns:
            ConversationState reconstruído
        """
        state_dict = json.loads(data.decode("utf-8"))
        
        # Reconstruir histórico
        history = []
        for turn_data in state_dict.get("history", []):
            history.append(
                ChatTurn(
                    user_message=Message(
                        role=Role(turn_data["user_message"]["role"]),
                        content=turn_data["user_message"]["content"],
                    ),
                    assistant_message=Message(
                        role=Role(turn_data["assistant_message"]["role"]),
                        content=turn_data["assistant_message"]["content"],
                    ),
                )
            )
        
        # Reconstruir dados de inscrição
        reg_data_dict = state_dict.get("registration_data", {})
        registration_data = RegistrationData(
            full_name=reg_data_dict.get("full_name"),
            email=reg_data_dict.get("email"),
            cpf=reg_data_dict.get("cpf"),
            phone=reg_data_dict.get("phone"),
            city=reg_data_dict.get("city"),
            state=reg_data_dict.get("state"),
            profile=reg_data_dict.get("profile"),
        )
        
        # Reconstruir estado
        return ConversationState(
            user_id=state_dict["user_id"],
            history=history,
            registration_step=RegistrationStep(state_dict["registration_step"]),
            registration_data=registration_data,
            max_stored_turns=state_dict.get("max_stored_turns", self._max_stored_turns),
        )

    def get_or_create(self, user_id: str) -> ConversationState:
        """
        Recupera uma sessão existente ou cria uma nova.
        
        Args:
            user_id: ID do usuário (número do WhatsApp)
            
        Returns:
            ConversationState existente ou novo
        """
        key = f"session:{user_id}"
        
        try:
            data = self._redis.get(key)
            if data:
                state = self._deserialize_state(data)
                logger.debug(
                    f"Sessão recuperada do Redis: user_id={user_id}, "
                    f"turns={len(state.history)}"
                )
                return state
            else:
                # Criar nova sessão
                state = ConversationState(
                    user_id=user_id,
                    max_stored_turns=self._max_stored_turns,
                )
                # Salvar imediatamente com TTL
                self.save_session(user_id, state)
                logger.debug(f"Nova sessão criada no Redis: user_id={user_id}")
                return state
        except RedisError as e:
            logger.error(f"Erro ao recuperar sessão do Redis: user_id={user_id}, error={e}")
            # Em caso de erro, criar sessão temporária em memória
            # (fallback para não quebrar o fluxo)
            logger.warning(f"Usando sessão temporária em memória para user_id={user_id}")
            return ConversationState(
                user_id=user_id,
                max_stored_turns=self._max_stored_turns,
            )

    def save_session(self, user_id: str, state: ConversationState) -> None:
        """
        Salva uma sessão no Redis com TTL.
        
        Args:
            user_id: ID do usuário
            state: Estado da conversa a salvar
        """
        key = f"session:{user_id}"
        
        try:
            # Poda o histórico antes de salvar (garantir limite)
            if len(state.history) > self._max_stored_turns:
                state.history = trim_history(state.history, self._max_stored_turns)
            
            # Serializar e salvar
            data = self._serialize_state(state)
            self._redis.setex(key, self._session_ttl_seconds, data)
            
            logger.debug(
                f"Sessão salva no Redis: user_id={user_id}, "
                f"turns={len(state.history)}, ttl={self._session_ttl_seconds}s"
            )
        except RedisError as e:
            logger.error(f"Erro ao salvar sessão no Redis: user_id={user_id}, error={e}")
            # Não relançar erro para não quebrar o fluxo
            # A sessão será recriada na próxima chamada

    def clear_session(self, user_id: str) -> None:
        """
        Remove uma sessão do Redis.
        
        Args:
            user_id: ID do usuário
        """
        key = f"session:{user_id}"
        try:
            self._redis.delete(key)
            logger.debug(f"Sessão removida do Redis: user_id={user_id}")
        except RedisError as e:
            logger.error(f"Erro ao remover sessão do Redis: user_id={user_id}, error={e}")

