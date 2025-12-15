"""
Provedor de contexto para o bot "Amigo".

Este provedor cria um contexto completamente diferente do bot padrão:
- Personalidade casual e descontraída
- Não fala sobre eventos ou inscrições
- Foca em conversas amigáveis e naturais
- Para fins de validação e teste
"""
import logging
from typing import Optional, Any
from ..provider import ContextProvider, ContextResult
from app.domain.amigo import get_amigo_info, get_mock_amigo_info

logger = logging.getLogger(__name__)


class AmigoContextProvider(ContextProvider):
    """
    Provedor de contexto para o bot "Amigo".
    
    Cria um contexto completamente diferente do bot padrão,
    com personalidade casual, amigável e descontraída.
    """
    
    def __init__(self, mock_mode: bool = False):
        """
        Inicializa o provedor.
        
        Args:
            mock_mode: Se True, usa dados mockados para testes
        """
        self._mock_mode = mock_mode
        if mock_mode:
            self._amigo_info = get_mock_amigo_info()
            logger.info("AmigoContextProvider: usando dados mockados")
        else:
            self._amigo_info = get_amigo_info()
            logger.info("AmigoContextProvider: usando dados reais do amigo")
    
    @property
    def context_type(self) -> str:
        return "amigo"
    
    @property
    def priority(self) -> int:
        return 1  # Alta prioridade (substitui o base quando usado)
    
    def get_context(
        self,
        user_id: Optional[str] = None,
        message_text: Optional[str] = None,
        state: Optional[Any] = None,
        **kwargs
    ) -> Optional[ContextResult]:
        """
        Gera o contexto para o bot amigo.
        
        Returns:
            ContextResult com personalidade e regras do amigo
        """
        amigo_block = self._build_amigo_info_block()
        
        return ContextResult(
            content=amigo_block,
            priority=self.priority,
            section_name=None,  # Não precisa de seção, é o contexto principal
            metadata={
                "type": "amigo",
                "name": self._amigo_info["name"],
                "age": self._amigo_info["age"],
                "mock": self._mock_mode
            }
        )
    
    def _build_amigo_info_block(self) -> str:
        """
        Constrói o bloco de informações do amigo.
        
        Returns:
            String formatada com personalidade e regras do amigo
        """
        ai = self._amigo_info
        
        # Montar informações básicas
        info_parts = [
            f"Você é o {ai['name']}, um amigo virtual de {ai['age']} anos.",
            "",
            "SUA PERSONALIDADE:",
            f"- Estilo: {ai['personality']['style']}",
            f"- Comunicação: {ai['personality']['communication']}",
            f"- Nível de formalidade: {ai['personality']['formality_level']}",
            f"- Uso de emojis: {'Sim, use ocasionalmente' if ai['personality']['emoji_usage'] else 'Não'}",
            "",
            "SEUS INTERESSES:",
            "\n".join([f"- {interest}" for interest in ai['interests']]),
            "",
            "TÓPICOS QUE VOCÊ GOSTA DE CONVERSAR:",
            "\n".join([f"- {topic}" for topic in ai['favorite_topics']]),
            "",
            "EXPRESSÕES QUE VOCÊ USA:",
            "\n".join([f"- \"{phrase}\"" for phrase in ai['catchphrases']]),
            "",
            "REGRAS DE COMPORTAMENTO (MUITO IMPORTANTE):",
            "\n".join([f"- {rule}" for rule in ai['behavior_rules']]),
            "",
            "ESTILO DE CONVERSA:",
            ai['conversation_style'],
            "",
            "IMPORTANTE - O QUE VOCÊ NÃO É:",
            "- Você NÃO é um assistente de evento",
            "- Você NÃO fala sobre congressos, eventos ou inscrições",
            "- Você NÃO é um bot de atendimento ou suporte",
            "- Você NÃO vende nada",
            "- Você NÃO coleta dados para cadastro",
            "",
            "IMPORTANTE - O QUE VOCÊ É:",
            "- Você é um AMIGO para conversar",
            "- Você tem personalidade própria",
            "- Você pode ter opiniões (respeitosas)",
            "- Você pode fazer piadas leves",
            "- Você é genuíno e natural",
            "- Você se importa com a conversa",
            "",
            "DIRETRIZES DE RESPOSTA:",
            "- Responda sempre de forma natural e amigável",
            "- Use linguagem informal e descontraída",
            "- Seja genuíno, não seja robótico",
            "- Mostre interesse na conversa",
            "- Se não souber algo, seja honesto",
            "- Pode usar emojis ocasionalmente (mas não exagere)",
            "- Mantenha o tom de amigo, não de assistente",
            "- Se o usuário perguntar sobre eventos/congressos, diga educadamente que você não trabalha com isso",
            "- Foque em ter uma conversa agradável e natural"
        ]
        
        return "\n".join(info_parts)
