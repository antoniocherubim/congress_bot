"""
Gerenciador de contexto que orquestra múltiplos provedores.
"""
import logging
from typing import List, Optional, Dict, Any
from .provider import ContextProvider, ContextResult
from .types import ContextType, parse_context_types
from ..session_manager import ConversationState

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Gerenciador que orquestra múltiplos provedores de contexto.
    
    Permite combinar diferentes contextos de forma modular
    e construir o prompt final do sistema.
    """
    
    def __init__(self, providers: List[ContextProvider]):
        """
        Inicializa o gerenciador com uma lista de provedores.
        
        Args:
            providers: Lista de provedores de contexto
        """
        self._providers: Dict[str, ContextProvider] = {}
        for provider in providers:
            provider_type = provider.context_type
            if provider_type in self._providers:
                logger.warning(
                    f"Provedor duplicado para tipo '{provider_type}'. "
                    f"Substituindo pelo último."
                )
            self._providers[provider_type] = provider
        
        logger.info(
            f"ContextManager inicializado com {len(self._providers)} provedores: "
            f"{list(self._providers.keys())}"
        )
    
    def build_system_prompt(
        self,
        context_types: Optional[List[ContextType]] = None,
        user_id: Optional[str] = None,
        message_text: Optional[str] = None,
        state: Optional[ConversationState] = None,
        **kwargs
    ) -> str:
        """
        Constrói o prompt do sistema combinando contextos dos provedores.
        
        Args:
            context_types: Lista de tipos de contexto a incluir (None = todos)
            user_id: ID do usuário
            message_text: Texto da mensagem atual
            state: Estado da conversa
            **kwargs: Argumentos adicionais para os provedores
            
        Returns:
            String com o prompt completo do sistema
        """
        # Se não especificado, usar todos os provedores disponíveis
        if context_types is None:
            context_types = [ContextType.DEFAULT]
        
        # Mapear tipos para provedores
        providers_to_use = self._select_providers(context_types)
        
        # Coletar contextos de todos os provedores
        context_results: List[ContextResult] = []
        for provider in providers_to_use:
            try:
                result = provider.get_context(
                    user_id=user_id,
                    message_text=message_text,
                    state=state,
                    **kwargs
                )
                if result and result.content:
                    context_results.append(result)
            except Exception as e:
                logger.error(
                    f"Erro ao obter contexto do provedor '{provider.context_type}': {e}",
                    exc_info=True
                )
        
        # Ordenar por prioridade (menor = mais importante)
        context_results.sort(key=lambda r: r.priority)
        
        # Construir prompt final
        prompt_parts = []
        for result in context_results:
            formatted = result.format_section()
            if formatted:
                prompt_parts.append(formatted)
        
        final_prompt = "".join(prompt_parts)
        
        logger.debug(
            f"Prompt construído: user_id={user_id}, "
            f"context_types={[ct.value for ct in context_types]}, "
            f"num_sections={len(context_results)}"
        )
        
        return final_prompt.strip()
    
    def _select_providers(self, context_types: List[ContextType]) -> List[ContextProvider]:
        """
        Seleciona os provedores baseado nos tipos de contexto solicitados.
        
        Args:
            context_types: Lista de tipos de contexto
            
        Returns:
            Lista de provedores a usar
        """
        providers = []
        
        for context_type in context_types:
            if context_type == ContextType.DEFAULT:
                # DEFAULT = base + event_info + registration
                if "base" in self._providers:
                    providers.append(self._providers["base"])
                if "event_info" in self._providers:
                    providers.append(self._providers["event_info"])
                if "registration" in self._providers:
                    providers.append(self._providers["registration"])
            elif context_type == ContextType.EVENT_INFO:
                if "base" in self._providers:
                    providers.append(self._providers["base"])
                if "event_info" in self._providers:
                    providers.append(self._providers["event_info"])
            elif context_type == ContextType.REGISTRATION:
                if "base" in self._providers:
                    providers.append(self._providers["base"])
                if "registration" in self._providers:
                    providers.append(self._providers["registration"])
            elif context_type == ContextType.SUPPORT:
                # Suporte: base + event_info (sem registration)
                if "base" in self._providers:
                    providers.append(self._providers["base"])
                if "event_info" in self._providers:
                    providers.append(self._providers["event_info"])
            elif context_type == ContextType.SALES:
                # Vendas: base + event_info (sem registration)
                if "base" in self._providers:
                    providers.append(self._providers["base"])
                if "event_info" in self._providers:
                    providers.append(self._providers["event_info"])
            elif context_type == ContextType.AMIGO:
                # Amigo: apenas o provedor amigo (substitui o base)
                if "amigo" in self._providers:
                    providers.append(self._providers["amigo"])
            elif context_type == ContextType.CUSTOM:
                # Custom: apenas base (outros contextos devem ser adicionados via kwargs)
                if "base" in self._providers:
                    providers.append(self._providers["base"])
        
        # Remover duplicatas mantendo ordem
        seen = set()
        unique_providers = []
        for provider in providers:
            if id(provider) not in seen:
                seen.add(id(provider))
                unique_providers.append(provider)
        
        return unique_providers
    
    def add_provider(self, provider: ContextProvider) -> None:
        """
        Adiciona um novo provedor ao gerenciador.
        
        Args:
            provider: Provedor de contexto a adicionar
        """
        provider_type = provider.context_type
        if provider_type in self._providers:
            logger.warning(
                f"Substituindo provedor existente para tipo '{provider_type}'"
            )
        self._providers[provider_type] = provider
        logger.info(f"Provedor '{provider_type}' adicionado ao ContextManager")

