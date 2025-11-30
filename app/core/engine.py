import logging
from typing import Dict, Any
from .session_manager import InMemorySessionManager
from .models import Message, Role
from .registration_manager import RegistrationManager
from ..config import AppConfig
from ..infra.openai_client import LanguageModelClient
from ..infra.email_service import EmailService
from ..storage.database import create_session_factory

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
        self._sessions = InMemorySessionManager()
        self._lm_client = LanguageModelClient(config)
        
        # Extrair tipo de DB da URL (sem credenciais)
        db_type = "sqlite" if "sqlite" in config.database_url else "postgres" if "postgres" in config.database_url else "unknown"
        logger.info(
            f"ChatbotEngine inicializado: model={config.openai_model}, "
            f"database_type={db_type}, max_history_turns={config.max_history_turns}"
        )
        
        self._db_session_factory = create_session_factory(config.database_url)
        self._email_service = EmailService(config)
        self._registration_manager = RegistrationManager(
            db_session_factory=self._db_session_factory,
            email_service=self._email_service,
        )

    def handle_message(self, user_id: str, message_text: str) -> Dict[str, Any]:
        """
        Processa uma mensagem do usuário e retorna uma resposta.

        Retorno em dict pra ser fácil de usar tanto na API HTTP quanto em testes.
        """
        message_preview = message_text[:80] + "..." if len(message_text) > 80 else message_text
        logger.debug(
            f"handle_message iniciado: user_id={user_id}, "
            f"message_preview={message_preview}"
        )
        
        # 1. Recuperar estado da conversa
        state = self._sessions.get_or_create(user_id)

        # 2. Verificar se é parte do fluxo de inscrição
        logger.debug(
            f"Repassando mensagem para RegistrationManager: user_id={user_id}, "
            f"registration_step={state.registration_step}"
        )
        state, registration_reply = self._registration_manager.handle_message(
            state, message_text
        )

        # 3. Se houver resposta do fluxo de inscrição, usar ela
        if registration_reply:
            logger.info(
                f"Mensagem tratada pelo fluxo de inscrição: user_id={user_id}, "
                f"step={state.registration_step}"
            )
            logger.debug(
                f"Resposta do fluxo de inscrição: user_id={user_id}, "
                f"reply_preview={registration_reply[:100]}..."
            )
            state.add_turn(user_msg=message_text, assistant_msg=registration_reply)
            return {
                "user_id": user_id,
                "reply": registration_reply,
                "turns": len(state.history),
            }

        # 4. Caso contrário, seguir fluxo normal de IA
        logger.debug(
            f"Mensagem será encaminhada para modelo de linguagem: user_id={user_id}, "
            f"history_size={len(state.history)}"
        )
        
        # Construir contexto (histórico recente)
        history_messages = state.get_recent_messages(self._config.max_history_turns)

        # 5. Adicionar mensagem atual do usuário na fila de envio
        messages_for_model = history_messages + [
            Message(role=Role.USER, content=message_text)
        ]

        # 6. Chamar modelo de linguagem
        reply_text = self._lm_client.generate_reply(
            system_prompt=self._config.system_prompt,
            messages=messages_for_model,
        )

        logger.info(
            f"Resposta obtida da OpenAI: user_id={user_id}, "
            f"history_turns={len(state.history)}, "
            f"reply_length={len(reply_text)}"
        )
        logger.debug(
            f"Resposta da OpenAI (preview): user_id={user_id}, "
            f"reply_preview={reply_text[:100]}..."
        )

        # 7. Atualizar estado da conversa
        state.add_turn(user_msg=message_text, assistant_msg=reply_text)

        # 8. Retornar resposta com metadados mínimos
        return {
            "user_id": user_id,
            "reply": reply_text,
            "turns": len(state.history),
        }

