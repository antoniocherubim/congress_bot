"""
Provedor de contexto base (system prompt padrão).
"""
import logging
from typing import Optional, Any
from ..provider import ContextProvider, ContextResult
from app.config import AppConfig

logger = logging.getLogger(__name__)


class BaseSystemPromptProvider(ContextProvider):
    """
    Provedor do prompt base do sistema.
    
    Fornece o prompt fundamental que define a personalidade
    e comportamento básico do chatbot.
    """
    
    def __init__(self, config: AppConfig):
        """
        Inicializa o provedor com a configuração.
        
        Args:
            config: Configuração da aplicação
        """
        self._config = config
    
    @property
    def context_type(self) -> str:
        return "base"
    
    @property
    def priority(self) -> int:
        return 1  # Maior prioridade (sempre primeiro)
    
    def get_context(
        self,
        user_id: Optional[str] = None,
        message_text: Optional[str] = None,
        state: Optional[Any] = None,
        **kwargs
    ) -> Optional[ContextResult]:
        """
        Retorna o prompt base do sistema.
        
        Returns:
            ContextResult com o system prompt base
        """
        return ContextResult(
            content=self._config.system_prompt.strip(),
            priority=self.priority,
            section_name=None,  # Prompt base não precisa de seção
            metadata={"type": "base_system_prompt"}
        )

