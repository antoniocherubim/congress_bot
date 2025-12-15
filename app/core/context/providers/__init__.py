"""
Provedores de contexto específicos.
"""
from .base import BaseSystemPromptProvider
from .event_info import EventInfoContextProvider
from .registration import RegistrationContextProvider
from .amigo import AmigoContextProvider

__all__ = [
    "BaseSystemPromptProvider",
    "EventInfoContextProvider",
    "RegistrationContextProvider",
    "AmigoContextProvider",
]

