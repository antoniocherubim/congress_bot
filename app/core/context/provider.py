"""
Classe base para provedores de contexto.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ContextResult:
    """
    Resultado de um provedor de contexto.
    
    Attributes:
        content: Conteúdo do contexto (texto a ser adicionado ao prompt)
        priority: Prioridade (menor número = maior prioridade, usado para ordenação)
        section_name: Nome da seção (ex: "[Informações do evento]")
        metadata: Metadados adicionais (opcional)
    """
    content: str
    priority: int = 100  # Prioridade padrão (menor = mais importante)
    section_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def format_section(self) -> str:
        """
        Formata o contexto como uma seção do prompt.
        
        Returns:
            String formatada com seção e conteúdo
        """
        if not self.content or not self.content.strip():
            return ""
        
        if self.section_name:
            return f"\n\n{self.section_name}\n{self.content}"
        return f"\n\n{self.content}"


class ContextProvider(ABC):
    """
    Classe base abstrata para provedores de contexto.
    
    Cada provedor é responsável por gerar uma parte do contexto
    do sistema que será passado para o modelo de linguagem.
    
    Exemplos:
    - BaseSystemPromptProvider: Prompt base do sistema
    - EventInfoContextProvider: Informações do evento
    - RegistrationContextProvider: Contexto de inscrição
    """
    
    @abstractmethod
    def get_context(
        self,
        user_id: Optional[str] = None,
        message_text: Optional[str] = None,
        state: Optional[Any] = None,
        **kwargs
    ) -> Optional[ContextResult]:
        """
        Gera o contexto para o prompt.
        
        Args:
            user_id: ID do usuário (opcional)
            message_text: Texto da mensagem atual (opcional)
            state: Estado da conversa (opcional, tipo específico depende da implementação)
            **kwargs: Argumentos adicionais específicos do provedor
            
        Returns:
            ContextResult com o contexto gerado, ou None se não aplicável
        """
        pass
    
    @property
    @abstractmethod
    def context_type(self) -> str:
        """
        Retorna o tipo de contexto que este provedor fornece.
        
        Returns:
            String identificando o tipo (ex: "base", "event_info", "registration")
        """
        pass
    
    @property
    def priority(self) -> int:
        """
        Prioridade do provedor (menor = mais importante).
        
        Returns:
            Prioridade padrão (pode ser sobrescrita)
        """
        return 100

