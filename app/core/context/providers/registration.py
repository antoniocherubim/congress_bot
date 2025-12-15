"""
Provedor de contexto para fluxo de inscrição.
"""
import logging
from typing import Optional, Any
from ..provider import ContextProvider, ContextResult
from ...registration_manager import RegistrationFlowHint
from ...session_manager import ConversationState

logger = logging.getLogger(__name__)


class RegistrationContextProvider(ContextProvider):
    """
    Provedor de contexto para o fluxo de inscrição.
    
    Gera instruções e contexto baseado no estado atual
    do fluxo de inscrição do usuário.
    """
    
    @property
    def context_type(self) -> str:
        return "registration"
    
    @property
    def priority(self) -> int:
        return 30  # Alta prioridade (antes de event_info)
    
    def get_context(
        self,
        user_id: Optional[str] = None,
        message_text: Optional[str] = None,
        state: Optional[ConversationState] = None,
        flow_hint: Optional[RegistrationFlowHint] = None,
        **kwargs
    ) -> Optional[ContextResult]:
        """
        Gera o contexto de inscrição baseado no estado atual.
        
        Args:
            flow_hint: Hints do fluxo de inscrição (obrigatório)
            state: Estado da conversa (opcional, usado se flow_hint não fornecido)
            
        Returns:
            ContextResult com contexto de inscrição, ou None se não aplicável
        """
        if not flow_hint:
            return None
        
        registration_context_parts = []
        
        # Instrução do fluxo
        if flow_hint.instruction:
            registration_context_parts.append(flow_hint.instruction)
        
        # Campo atual esperado
        if flow_hint.current_field:
            registration_context_parts.append(
                f"No fluxo de inscrição, o campo atual esperado é: {flow_hint.current_field!r}."
            )
        
        # Dados já coletados
        if state:
            collected_data_summary = state.get_registration_summary()
            if collected_data_summary and collected_data_summary != "Nenhum dado coletado ainda.":
                registration_context_parts.append(
                    f"Dados de inscrição já coletados: {collected_data_summary}."
                )
        
        # Instruções de comportamento
        if flow_hint.in_registration_flow:
            registration_context_parts.append(
                "Você deve sempre responder de forma natural e humana, como um assistente do congresso. "
                "Se o usuário fizer uma pergunta ou sair do tema da inscrição, responda à dúvida com clareza e simpatia "
                "e, em seguida, conduza suavemente de volta ao próximo passo do fluxo de inscrição. "
                "Se o usuário forneceu claramente o dado esperado, confirme esse dado e avance naturalmente para o próximo campo. "
                "IMPORTANTE: Durante o fluxo de inscrição, NÃO mencione pagamento ou próximos passos de pagamento. "
                "O bot apenas coleta os dados do participante. O pagamento (se necessário) será feito posteriormente na área do usuário do site oficial."
            )
        elif flow_hint.instruction:
            # Mesmo fora do fluxo ativo, se há uma instrução (ex: CPF duplicado), siga ela
            registration_context_parts.append(
                "Siga a instrução acima de forma natural e humana."
            )
        
        if not registration_context_parts:
            return None
        
        return ContextResult(
            content="\n".join(registration_context_parts),
            priority=self.priority,
            section_name="[Contexto do fluxo de inscrição]",
            metadata={
                "type": "registration",
                "in_registration_flow": flow_hint.in_registration_flow,
                "current_field": flow_hint.current_field,
                "field_captured": flow_hint.field_captured,
            }
        )

