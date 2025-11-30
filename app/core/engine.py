from typing import Dict, Any
from .session_manager import InMemorySessionManager
from .models import Message, Role
from .registration_manager import RegistrationManager
from ..config import AppConfig
from ..infra.openai_client import LanguageModelClient
from ..infra.email_service import EmailService
from ..storage.database import create_session_factory


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
        # 1. Recuperar estado da conversa
        state = self._sessions.get_or_create(user_id)

        # 2. Verificar se é parte do fluxo de inscrição
        state, registration_reply = self._registration_manager.handle_message(
            state, message_text
        )

        # 3. Se houver resposta do fluxo de inscrição, usar ela
        if registration_reply:
            state.add_turn(user_msg=message_text, assistant_msg=registration_reply)
            return {
                "user_id": user_id,
                "reply": registration_reply,
                "turns": len(state.history),
            }

        # 4. Caso contrário, seguir fluxo normal de IA
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

        # 7. Atualizar estado da conversa
        state.add_turn(user_msg=message_text, assistant_msg=reply_text)

        # 8. Retornar resposta com metadados mínimos
        return {
            "user_id": user_id,
            "reply": reply_text,
            "turns": len(state.history),
        }

