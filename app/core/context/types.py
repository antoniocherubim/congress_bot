"""
Tipos e constantes para o sistema de contexto.
"""
from enum import Enum
from typing import List, Optional


class ContextType(str, Enum):
    """
    Tipos de contexto disponíveis para o chatbot.
    
    Cada tipo representa uma função ou domínio específico do chatbot.
    """
    # Contexto padrão (evento + inscrição)
    DEFAULT = "default"
    
    # Apenas informações do evento (FAQ)
    EVENT_INFO = "event_info"
    
    # Apenas fluxo de inscrição
    REGISTRATION = "registration"
    
    # Suporte técnico
    SUPPORT = "support"
    
    # Vendas/comercial
    SALES = "sales"
    
    # Personalizado (para extensões futuras)
    CUSTOM = "custom"
    
    # Bot amigo (para validação - personalidade casual e descontraída)
    AMIGO = "amigo"


def parse_context_types(context_type: Optional[str]) -> List[ContextType]:
    """
    Parse uma string de tipos de contexto para lista.
    
    Suporta:
    - String única: "default"
    - Lista separada por vírgula: "event_info,registration"
    - Lista de strings: ["event_info", "registration"]
    
    Args:
        context_type: String ou lista de tipos de contexto
        
    Returns:
        Lista de ContextType
        
    Raises:
        ValueError: Se o tipo não for válido
    """
    if context_type is None:
        return [ContextType.DEFAULT]
    
    if isinstance(context_type, list):
        types = context_type
    elif isinstance(context_type, str):
        # Separar por vírgula se houver múltiplos
        types = [t.strip() for t in context_type.split(",") if t.strip()]
    else:
        raise ValueError(f"Tipo de contexto inválido: {context_type}")
    
    # Validar e converter para enum
    result = []
    for t in types:
        try:
            result.append(ContextType(t.lower()))
        except ValueError:
            raise ValueError(
                f"Tipo de contexto inválido: '{t}'. "
                f"Tipos válidos: {[e.value for e in ContextType]}"
            )
    
    return result if result else [ContextType.DEFAULT]

