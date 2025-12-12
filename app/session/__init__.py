"""
Módulo de gerenciamento de sessões.
Suporta tanto InMemorySessionManager quanto RedisSessionManager.
"""

from .redis_session_manager import RedisSessionManager
from ..core.session_manager import InMemorySessionManager

__all__ = ["RedisSessionManager", "InMemorySessionManager"]

