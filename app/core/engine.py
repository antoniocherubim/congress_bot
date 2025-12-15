import logging
from typing import Dict, Any, Optional, List
from .session_manager import InMemorySessionManager
from ..session.redis_session_manager import RedisSessionManager
from .models import Message, Role
from .registration_manager import RegistrationManager, RegistrationFlowHint
from ..config import AppConfig
from ..infra.openai_client import LanguageModelClient
from ..infra.email_service import EmailService
from ..storage.database import create_session_factory
from .context import (
    ContextManager,
    ContextType,
    parse_context_types,
    BaseSystemPromptProvider,
    EventInfoContextProvider,
    RegistrationContextProvider,
    AmigoContextProvider,
)

logger = logging.getLogger(__name__)


class ChatbotEngine:
    """
    Núcleo lógico do chatbot.

    - Orquestra sessão do usuário
    - Monta contexto para o modelo
    - Faz a chamada ao LanguageModelClient
    - Gerencia fluxo de inscrição via RegistrationManager
    - Retorna resposta + metadados (lugar perfeito para o ACE crescer depois)
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        
        # Escolher gerenciador de sessões: Redis se configurado, senão InMemory
        if config.redis_url and config.redis_url.strip():
            try:
                self._sessions = RedisSessionManager(
                    redis_url=config.redis_url,
                    max_stored_turns=config.session_max_stored_turns,
                    session_ttl_seconds=config.session_ttl_seconds,
                )
                logger.info(f"Sessões usando Redis: url={config.redis_url}")
            except Exception as e:
                logger.error(f"Erro ao inicializar RedisSessionManager: {e}, usando InMemory como fallback")
                self._sessions = InMemorySessionManager(max_stored_turns=config.session_max_stored_turns)
        else:
            self._sessions = InMemorySessionManager(max_stored_turns=config.session_max_stored_turns)
            logger.info("Sessões usando armazenamento em memória (REDIS_URL não configurado)")
        
        self._lm_client = LanguageModelClient(config)
        
        # Extrair tipo de DB da URL (sem credenciais)
        db_type = "sqlite" if "sqlite" in config.database_url else "postgres" if "postgres" in config.database_url else "unknown"
        logger.info(
            f"ChatbotEngine inicializado: model={config.openai_model}, "
            f"database_type={db_type}, max_history_turns={config.max_history_turns}"
        )
        
        # Em produção, não criar tabelas automaticamente (usar Alembic)
        # Em dev, permitir criação automática se necessário
        create_tables = config.env == "dev"
        self._db_session_factory = create_session_factory(config.database_url, create_tables=create_tables)
        self._email_service = EmailService(config)
        self._registration_manager = RegistrationManager(
            db_session_factory=self._db_session_factory,
            email_service=self._email_service,
        )

        # Inicializar ContextManager com provedores
        self._context_manager = self._create_context_manager(config)

    def _create_context_manager(self, config: AppConfig) -> ContextManager:
        """
        Cria e configura o ContextManager com todos os provedores.
        
        Args:
            config: Configuração da aplicação
            
        Returns:
            ContextManager configurado
        """
        providers = [
            BaseSystemPromptProvider(config),
            EventInfoContextProvider(mock_event_data=config.mock_event_data),
            RegistrationContextProvider(),
            AmigoContextProvider(mock_mode=False),  # Bot amigo para validação
        ]
        return ContextManager(providers)
    
    def handle_message(
        self,
        user_id: str,
        message_text: str,
        request_id: Optional[str] = None,
        context_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processa uma mensagem do usuário e retorna uma resposta.

        Retorno em dict pra ser fácil de usar tanto na API HTTP quanto em testes.
        
        Agora sempre usa o modelo de linguagem, guiado por hints do fluxo de inscrição.
        """
        message_preview = message_text[:80] + "..." if len(message_text) > 80 else message_text
        logger.debug(
            f"handle_message iniciado: user_id={user_id}, "
            f"message_preview={message_preview}"
        )
        
        # 1. Recuperar estado da conversa
        state = self._sessions.get_or_create(user_id)

        # 2. Processar mensagem no contexto do fluxo de inscrição
        logger.debug(
            f"Repassando mensagem para RegistrationManager: user_id={user_id}, "
            f"registration_step={state.registration_step}"
        )
        flow_hint = self._registration_manager.handle_message(state, message_text)
        state = flow_hint.state

        # 3. Parse tipos de contexto solicitados
        context_types = parse_context_types(context_type)
        
        # 4. Construir prompt usando ContextManager
        hybrid_system_prompt = self._context_manager.build_system_prompt(
            context_types=context_types,
            user_id=user_id,
            message_text=message_text,
            state=state,
            flow_hint=flow_hint,
        )
        
        logger.debug(
            f"Prompt construído: user_id={user_id}, "
            f"context_types={[ct.value for ct in context_types]}, "
            f"in_registration_flow={flow_hint.in_registration_flow}, "
            f"current_field={flow_hint.current_field}"
        )

        # 5. Construir contexto (histórico recente)
        history_messages = state.get_recent_messages(self._config.max_history_turns)

        # 6. Adicionar mensagem atual do usuário na fila de envio
        messages_for_model = history_messages + [
            Message(role=Role.USER, content=message_text)
        ]

        # 7. Chamar modelo de linguagem SEMPRE
        logger.debug(
            f"Mensagem será encaminhada para modelo de linguagem: user_id={user_id}, "
            f"history_size={len(state.history)}, request_id={request_id or 'N/A'}"
        )
        
        reply_text = self._lm_client.generate_reply(
            system_prompt=hybrid_system_prompt,
            messages=messages_for_model,
            request_id=request_id,
        )

        logger.info(
            f"Resposta obtida da OpenAI: user_id={user_id}, "
            f"history_turns={len(state.history)}, "
            f"reply_length={len(reply_text)}, "
            f"in_registration_flow={flow_hint.in_registration_flow}"
        )
        logger.debug(
            f"Resposta da OpenAI (preview): user_id={user_id}, "
            f"reply_preview={reply_text[:100]}..."
        )

        # 8. Atualizar estado da conversa (com poda automática)
        state.add_turn(
            user_msg=message_text,
            assistant_msg=reply_text,
            max_stored_turns=self._config.session_max_stored_turns
        )
        
        # 9. Salvar sessão (especialmente importante para Redis)
        # InMemorySessionManager não precisa de save explícito, mas RedisSessionManager sim
        if isinstance(self._sessions, RedisSessionManager):
            self._sessions.save_session(user_id, state)

        # 10. Retornar resposta com metadados mínimos
        return {
            "user_id": user_id,
            "reply": reply_text,
            "turns": len(state.history),
        }
    
    def get_conversation_history(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Recupera o histórico de conversas de um usuário sem processar mensagem.
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Dict com histórico, estado de registro e metadados
        """
        # Recuperar estado da conversa
        state = self._sessions.get_or_create(user_id)
        
        # Converter histórico para formato serializável
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
        
        # Converter dados de registro para dict
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
        
        return {
            "user_id": state.user_id,
            "turns": len(state.history),
            "history": history_data,
            "registration_step": state.registration_step.value,
            "registration_data": registration_data_dict,
        }

