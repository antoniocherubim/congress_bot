from typing import Dict, Any
from .session_manager import InMemorySessionManager
from .models import Message, Role
from ..config import AppConfig
from ..infra.openai_client import LanguageModelClient


class ChatbotEngine:
    """
    Núcleo lógico do chatbot.

    - Orquestra sessão do usuário
    - Monta contexto para o modelo
    - Faz a chamada ao LanguageModelClient
    - Retorna resposta + metadados (lugar perfeito para o ACE crescer depois)
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._sessions = InMemorySessionManager()
        self._lm_client = LanguageModelClient(config)

    def handle_message(self, user_id: str, message_text: str) -> Dict[str, Any]:
        """
        Processa uma mensagem do usuário e retorna uma resposta.

        Retorno em dict pra ser fácil de usar tanto na API HTTP quanto em testes.
        """
        # 1. Recuperar estado da conversa
        state = self._sessions.get_or_create(user_id)

        # 2. Construir contexto (histórico recente)
        history_messages = state.get_recent_messages(self._config.max_history_turns)

        # 3. Adicionar mensagem atual do usuário na fila de envio
        messages_for_model = history_messages + [
            Message(role=Role.USER, content=message_text)
        ]

        # 4. Chamar modelo de linguagem
        reply_text = self._lm_client.generate_reply(
            system_prompt=self._config.system_prompt,
            messages=messages_for_model,
        )

        # 5. Atualizar estado da conversa
        state.add_turn(user_msg=message_text, assistant_msg=reply_text)

        # 6. Retornar resposta com metadados mínimos
        return {
            "user_id": user_id,
            "reply": reply_text,
            "turns": len(state.history),
        }

