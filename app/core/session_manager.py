import logging
from typing import Dict, List
from dataclasses import dataclass, field
from .models import Message, ChatTurn, Role
from .registration_state import RegistrationStep, RegistrationData

logger = logging.getLogger(__name__)


def trim_history(history: List[ChatTurn], max_turns: int) -> List[ChatTurn]:
    """
    Poda o histórico mantendo apenas os últimos max_turns turnos.
    
    Args:
        history: Lista de turnos de conversa
        max_turns: Número máximo de turnos a manter
        
    Returns:
        Lista podada com no máximo max_turns turnos
    """
    if len(history) <= max_turns:
        return history
    return history[-max_turns:]


@dataclass
class ConversationState:
    """
    Estado da conversa de um usuário.
    Guardado em memória nesse MVP.
    Futuro: mover para banco (Postgres, Redis, etc).
    """
    user_id: str
    history: List[ChatTurn] = field(default_factory=list)
    registration_step: RegistrationStep = RegistrationStep.IDLE
    registration_data: RegistrationData = field(default_factory=RegistrationData)
    max_stored_turns: int = 30  # Limite padrão de turnos armazenados

    def add_turn(self, user_msg: str, assistant_msg: str, max_stored_turns: int = None) -> None:
        """
        Adiciona um novo turno ao histórico e poda se necessário.
        
        Args:
            user_msg: Mensagem do usuário
            assistant_msg: Resposta do assistente
            max_stored_turns: Limite de turnos a manter (usa self.max_stored_turns se None)
        """
        self.history.append(
            ChatTurn(
                user_message=Message(role=Role.USER, content=user_msg),
                assistant_message=Message(role=Role.ASSISTANT, content=assistant_msg),
            )
        )
        # Poda o histórico após adicionar
        limit = max_stored_turns if max_stored_turns is not None else self.max_stored_turns
        if len(self.history) > limit:
            old_size = len(self.history)
            self.history = trim_history(self.history, limit)
            logger.debug(
                f"Histórico podado: user_id={self.user_id}, "
                f"de {old_size} para {len(self.history)} turnos"
            )

    def get_recent_messages(self, max_turns: int) -> List[Message]:
        """
        Retorna os últimos N turnos em formato de lista de mensagens
        intercalando usuário/assistente, para mandar ao modelo.
        """
        recent = self.history[-max_turns:]
        messages: List[Message] = []
        for turn in recent:
            messages.append(turn.user_message)
            messages.append(turn.assistant_message)
        return messages

    def get_registration_summary(self) -> str:
        """
        Retorna um resumo dos dados de inscrição já coletados.
        Usado para fornecer contexto ao modelo de linguagem.
        """
        data = self.registration_data
        parts = []
        
        if data.full_name:
            parts.append(f"Nome: {data.full_name}")
        if data.email:
            parts.append(f"E-mail: {data.email}")
        if data.cpf:
            parts.append(f"CPF: {data.cpf}")
        if data.phone:
            parts.append(f"Telefone: {data.phone}")
        if data.city:
            city_state = f"{data.city}"
            if data.state:
                city_state += f"/{data.state}"
            parts.append(f"Cidade/UF: {city_state}")
        if data.profile:
            parts.append(f"Perfil: {data.profile}")
        
        if not parts:
            return "Nenhum dado coletado ainda."
        
        return "; ".join(parts)


class InMemorySessionManager:
    """
    Gerenciador simples de sessões em memória.
    Em produção, isso seria substituído por storage persistente.
    """

    def __init__(self, max_stored_turns: int = 30) -> None:
        self._sessions: Dict[str, ConversationState] = {}
        self._max_stored_turns = max_stored_turns

    def get_or_create(self, user_id: str) -> ConversationState:
        if user_id not in self._sessions:
            logger.debug(f"Nova ConversationState criada: user_id={user_id}")
            self._sessions[user_id] = ConversationState(
                user_id=user_id,
                max_stored_turns=self._max_stored_turns
            )
        else:
            logger.debug(f"ConversationState recuperada: user_id={user_id}, turns={len(self._sessions[user_id].history)}")
        return self._sessions[user_id]

