from dataclasses import dataclass
from enum import Enum
from typing import List


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    role: Role
    content: str


@dataclass
class ChatTurn:
    """
    Representa um turno de conversa (usuário -> assistente).
    Pode ser expandido depois com metadados (timestamp, tokens, etc.).
    """
    user_message: Message
    assistant_message: Message

