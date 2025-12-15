"""
Provedor de contexto com informações do evento.
"""
import logging
from typing import Optional, Any, Dict
from ..provider import ContextProvider, ContextResult
from app.domain.event_info import get_event_info, get_mock_event_info, EventInfo

logger = logging.getLogger(__name__)


class EventInfoContextProvider(ContextProvider):
    """
    Provedor de contexto com informações do evento.
    
    Carrega e formata informações do evento (reais ou mockadas)
    para incluir no prompt do sistema.
    """
    
    def __init__(self, mock_event_data: bool = False):
        """
        Inicializa o provedor.
        
        Args:
            mock_event_data: Se True, usa dados mockados; senão, usa dados reais
        """
        self._mock_event_data = mock_event_data
        self._event_info: Optional[Dict[str, Any]] = None
        self._mock_event_info: Optional[EventInfo] = None
        
        if mock_event_data:
            self._mock_event_info = get_mock_event_info()
            logger.info("EventInfoContextProvider: usando dados mockados")
        else:
            self._event_info = get_event_info()
            logger.info("EventInfoContextProvider: usando dados reais do evento")
    
    @property
    def context_type(self) -> str:
        return "event_info"
    
    @property
    def priority(self) -> int:
        return 50  # Prioridade média
    
    def get_context(
        self,
        user_id: Optional[str] = None,
        message_text: Optional[str] = None,
        state: Optional[Any] = None,
        **kwargs
    ) -> Optional[ContextResult]:
        """
        Gera o contexto com informações do evento.
        
        Returns:
            ContextResult com informações formatadas do evento
        """
        event_info_block = self._build_event_info_block()
        
        if not event_info_block:
            return None
        
        return ContextResult(
            content=event_info_block,
            priority=self.priority,
            section_name="[Informações do evento BioSummit 2026]",
            metadata={"type": "event_info", "mock": self._mock_event_data}
        )
    
    def _build_event_info_block(self) -> str:
        """
        Constrói o bloco de informações do evento.
        
        Returns:
            String formatada com informações do evento
        """
        if self._mock_event_info is not None:
            return self._format_mock_event_info()
        elif self._event_info is not None:
            return self._format_real_event_info()
        return ""
    
    def _format_mock_event_info(self) -> str:
        """Formata informações mockadas do evento."""
        ei = self._mock_event_info
        ticket_lines = [
            f"- {cat.name}: R$ {cat.price_brl:.2f} – {cat.description} ({cat.notes})"
            for cat in ei.ticket_categories
        ]
        agenda_lines = [f"- {item}" for item in ei.agenda_highlights]
        
        faq_lines = [
            f"- {key.replace('_', ' ').title()}: {value}"
            for key, value in ei.faq_extra.items()
        ]
        
        return (
            "ATENÇÃO: As informações abaixo são SIMULADAS para ambiente de teste e não representam necessariamente os valores finais do evento.\n\n"
            "IMPORTANTE: Quando o modo de dados simulados está ativo, você DEVE usar as informações abaixo para responder perguntas sobre valores, preços de inscrição, categorias de ingresso e outras informações do evento. "
            "Não diga 'Não tenho essa informação' quando os dados simulados estiverem disponíveis neste bloco.\n\n"
            f"Nome do evento: {ei.name} ({ei.edition})\n"
            f"Datas: {ei.dates}\n"
            f"Local: {ei.location}\n"
            f"Tema: {ei.theme}\n"
            f"Contato (e-mail): {ei.contact_email}\n"
            f"Contato (WhatsApp): {ei.contact_whatsapp}\n"
            f"Site: {ei.website}\n\n"
            "Categorias de ingresso e valores simulados:\n"
            + "\n".join(ticket_lines)
            + "\n\nPrincipais destaques de agenda (simulados):\n"
            + "\n".join(agenda_lines)
            + "\n\nInformações adicionais (simuladas):\n"
            + "\n".join(faq_lines)
        )
    
    def _format_real_event_info(self) -> str:
        """Formata informações reais do evento."""
        ei = self._event_info
        
        # Formatar informações de datas
        dates_info = f"{ei['dates']['display']} ({ei['dates']['start']} a {ei['dates']['end']})"
        if 'time_window' in ei['dates']:
            dates_info += f", das {ei['dates']['time_window']['start_time']} às {ei['dates']['time_window']['end_time']}"
        
        # Formatar informações de local
        location_info = ei['location']['display']
        if 'description' in ei['location']:
            location_info += f" - {ei['location']['description']}"
        
        # Formatar categorias de ingressos e preços
        ticket_sections = []
        for category in ei['tickets']['categories']:
            price_lines = []
            for price in category['prices']:
                price_str = f"R$ {price['amount']:.2f}"
                if 'label' in price:
                    price_str += f" ({price['label']})"
                price_lines.append(price_str)
            ticket_sections.append(
                f"- {category['name']}: " + " / ".join(price_lines)
            )
        
        # Formatar destaques de estrutura
        structure_lines = []
        if 'structure_highlights' in ei:
            if 'area_m2' in ei['structure_highlights']:
                structure_lines.append(f"Área total: {ei['structure_highlights']['area_m2']} m²")
            if 'features' in ei['structure_highlights']:
                structure_lines.extend([f"- {item}" for item in ei['structure_highlights']['features']])
        
        # Formatar público-alvo
        audience_lines = [f"- {item}" for item in ei['target_audience']]
        
        # Montar bloco de informações
        event_info_parts = [
            f"Nome: {ei['name']}",
            f"Tema: {ei['theme']}",
            f"Datas: {dates_info}",
            f"Local: {location_info}",
            f"Formato: {ei['format']['type']}",
            "",
            "Descrição:",
            ei['description'],
            "",
            "Público-alvo:",
            "\n".join(audience_lines),
            "",
            "Estrutura e destaques:",
            "\n".join(structure_lines),
            "",
            "Organização:",
            f"Nome: {ei['organizer']['name']} ({ei['organizer']['brand']})",
            f"Telefone: {ei['organizer']['phone']}",
            f"E-mail: {ei['organizer']['email']}",
            f"Site: {ei['organizer']['website']}",
            "",
            "Categorias de ingresso e valores:",
            "\n".join(ticket_sections),
        ]
        
        # Adicionar informações opcionais
        self._add_optional_sections(ei, event_info_parts)
        
        return "\n".join(event_info_parts)
    
    def _add_optional_sections(self, ei: Dict, event_info_parts: list) -> None:
        """Adiciona seções opcionais do evento."""
        # Status de inscrições
        if 'status' in ei['tickets']:
            event_info_parts.append("")
            event_info_parts.append("Status de inscrições:")
            if 'message' in ei['tickets']['status']:
                event_info_parts.append(f"- {ei['tickets']['status']['message']}")
            if 'note' in ei['tickets']['status']:
                event_info_parts.append(f"- {ei['tickets']['status']['note']}")
        
        # Política de cancelamento
        if 'cancellation_policy' in ei['tickets']:
            event_info_parts.append("")
            event_info_parts.append("Política de cancelamento:")
            event_info_parts.append(f"- {ei['tickets']['cancellation_policy']}")
        
        # Processo de inscrição
        if 'registration_process' in ei['tickets']:
            event_info_parts.append("")
            event_info_parts.append("Processo de inscrição:")
            if 'description' in ei['tickets']['registration_process']:
                event_info_parts.append(ei['tickets']['registration_process']['description'])
            if 'user_area_instructions' in ei['tickets']['registration_process']:
                event_info_parts.append(f"Instrução: {ei['tickets']['registration_process']['user_area_instructions']}")
        
        # Recomendações para o bot
        if 'recommendation_for_bot' in ei['tickets']:
            event_info_parts.append("")
            event_info_parts.append("Recomendação: " + ei['tickets']['recommendation_for_bot'])
        
        # Palestrantes
        if 'speakers_page' in ei:
            event_info_parts.append("")
            event_info_parts.append("Palestrantes:")
            event_info_parts.append(f"Página: {ei['speakers_page']['url']}")
            if 'note' in ei['speakers_page']:
                event_info_parts.append(f"Nota: {ei['speakers_page']['note']}")
        
        # Comitê Técnico
        if 'technical_committee' in ei:
            event_info_parts.append("")
            event_info_parts.append("Comitê Técnico:")
            if 'description' in ei['technical_committee']:
                event_info_parts.append(ei['technical_committee']['description'])
            if 'members' in ei['technical_committee']:
                for member in ei['technical_committee']['members']:
                    member_info = f"- {member['name']}"
                    if 'institution' in member:
                        member_info += f" ({member['institution']})"
                    event_info_parts.append(member_info)
        
        # Patrocínio
        if 'sponsorship' in ei:
            event_info_parts.append("")
            event_info_parts.append("Patrocínio:")
            event_info_parts.append(f"Página: {ei['sponsorship']['url']}")
            if 'qualified_audience_over' in ei['sponsorship']:
                event_info_parts.append(f"Público estimado: mais de {ei['sponsorship']['qualified_audience_over']} participantes")
            if 'benefits' in ei['sponsorship']:
                event_info_parts.append("Benefícios:")
                event_info_parts.extend([f"- {item}" for item in ei['sponsorship']['benefits']])
            if 'note' in ei['sponsorship']:
                event_info_parts.append(f"Nota: {ei['sponsorship']['note']}")
        
        # Área do usuário
        if 'user_area' in ei:
            event_info_parts.append("")
            event_info_parts.append("Área do usuário:")
            event_info_parts.append(f"URL: {ei['user_area']['url']}")
            if 'features' in ei['user_area']:
                event_info_parts.append("Funcionalidades:")
                event_info_parts.extend([f"- {item}" for item in ei['user_area']['features']])

