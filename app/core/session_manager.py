from typing import Dict, List
from dataclasses import dataclass, field
from .models import Message, ChatTurn, Role


@dataclass
class ConversationState:
    """
    Estado da conversa de um usuário.
    Guardado em memória nesse MVP.
    Futuro: mover para banco (Postgres, Redis, etc).
    """
    user_id: str
    history: List[ChatTurn] = field(default_factory=list)

    def add_turn(self, user_msg: str, assistant_msg: str) -> None:
        self.history.append(
            ChatTurn(
                user_message=Message(role=Role.USER, content=user_msg),
                assistant_message=Message(role=Role.ASSISTANT, content=assistant_msg),
            )
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


class InMemorySessionManager:
    """
    Gerenciador simples de sessões em memória.
    Em produção, isso seria substituído por storage persistente.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, ConversationState] = {}

    def get_or_create(self, user_id: str) -> ConversationState:
        if user_id not in self._sessions:
            self._sessions[user_id] = ConversationState(user_id=user_id)
        return self._sessions[user_id]

