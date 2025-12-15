"""
Módulo de gerenciamento de contexto do chatbot.

Permite criar diferentes contextos e combiná-los de forma modular.
"""

from .types import ContextType, parse_context_types
from .provider import ContextProvider, ContextResult
from .manager import ContextManager
from .providers import (
    BaseSystemPromptProvider,
    EventInfoContextProvider,
    RegistrationContextProvider,
    AmigoContextProvider,
)

__all__ = [
    "ContextType",
    "parse_context_types",
    "ContextProvider",
    "ContextResult",
    "ContextManager",
    "BaseSystemPromptProvider",
    "EventInfoContextProvider",
    "RegistrationContextProvider",
    "AmigoContextProvider",
]

