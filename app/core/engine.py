import logging
from typing import Dict, Any, Optional
from .session_manager import InMemorySessionManager
from .models import Message, Role
from .registration_manager import RegistrationManager, RegistrationFlowHint
from ..config import AppConfig
from ..infra.openai_client import LanguageModelClient
from ..infra.email_service import EmailService
from ..storage.database import create_session_factory
from ..domain.event_info import get_event_info, get_mock_event_info, EventInfo

logger = logging.getLogger(__name__)


class ChatbotEngine:
    """
    Núcleo lógico do chatbot.

    - Orquestra sessão do usuário
    - Monta contexto para o modelo
    - Faz a chamada ao LanguageModelClient
    - Gerencia fluxo de inscrição via RegistrationManager
    - Retorna resposta + metadados (lugar perfeito para o ACE crescer depois)
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._sessions = InMemorySessionManager()
        self._lm_client = LanguageModelClient(config)
        
        # Extrair tipo de DB da URL (sem credenciais)
        db_type = "sqlite" if "sqlite" in config.database_url else "postgres" if "postgres" in config.database_url else "unknown"
        logger.info(
            f"ChatbotEngine inicializado: model={config.openai_model}, "
            f"database_type={db_type}, max_history_turns={config.max_history_turns}"
        )
        
        # Carregar informações do evento (reais ou mockadas)
        self._event_info: Optional[Dict[str, Any]] = None
        self._mock_event_info: Optional[EventInfo] = None
        
        if config.mock_event_data:
            self._mock_event_info = get_mock_event_info()
            logger.info("Mock de dados do evento habilitado (BIOSUMMIT_MOCK_EVENT_DATA=True).")
        else:
            self._event_info = get_event_info()
            logger.info("Carregando informações reais do evento BioSummit 2026.")
        
        self._db_session_factory = create_session_factory(config.database_url)
        self._email_service = EmailService(config)
        self._registration_manager = RegistrationManager(
            db_session_factory=self._db_session_factory,
            email_service=self._email_service,
        )

    def handle_message(self, user_id: str, message_text: str) -> Dict[str, Any]:
        """
        Processa uma mensagem do usuário e retorna uma resposta.

        Retorno em dict pra ser fácil de usar tanto na API HTTP quanto em testes.
        
        Agora sempre usa o modelo de linguagem, guiado por hints do fluxo de inscrição.
        """
        message_preview = message_text[:80] + "..." if len(message_text) > 80 else message_text
        logger.debug(
            f"handle_message iniciado: user_id={user_id}, "
            f"message_preview={message_preview}"
        )
        
        # 1. Recuperar estado da conversa
        state = self._sessions.get_or_create(user_id)

        # 2. Processar mensagem no contexto do fluxo de inscrição
        logger.debug(
            f"Repassando mensagem para RegistrationManager: user_id={user_id}, "
            f"registration_step={state.registration_step}"
        )
        flow_hint = self._registration_manager.handle_message(state, message_text)
        state = flow_hint.state

        # 3. Construir prompt híbrido combinando system_prompt base com contexto de inscrição
        registration_context_parts = []
        
        if flow_hint.instruction:
            registration_context_parts.append(flow_hint.instruction)
        
        if flow_hint.current_field:
            registration_context_parts.append(
                f"No fluxo de inscrição, o campo atual esperado é: {flow_hint.current_field!r}."
            )
        
        # Incluir dados já coletados
        collected_data_summary = state.get_registration_summary()
        if collected_data_summary and collected_data_summary != "Nenhum dado coletado ainda.":
            registration_context_parts.append(
                f"Dados de inscrição já coletados: {collected_data_summary}."
            )
        
        # Instrução de meta-comportamento
        if flow_hint.in_registration_flow:
            registration_context_parts.append(
                "Você deve sempre responder de forma natural e humana, como um assistente do congresso. "
                "Se o usuário fizer uma pergunta ou sair do tema da inscrição, responda à dúvida com clareza e simpatia "
                "e, em seguida, conduza suavemente de volta ao próximo passo do fluxo de inscrição. "
                "Se o usuário forneceu claramente o dado esperado, confirme esse dado e avance naturalmente para o próximo campo."
            )
        elif flow_hint.instruction:
            # Mesmo fora do fluxo ativo, se há uma instrução (ex: CPF duplicado), siga ela
            registration_context_parts.append(
                "Siga a instrução acima de forma natural e humana."
            )

        # Montar prompt híbrido
        hybrid_system_prompt = self._config.system_prompt
        if registration_context_parts:
            hybrid_system_prompt = (
                self._config.system_prompt
                + "\n\n[Contexto do fluxo de inscrição]\n"
                + "\n".join(registration_context_parts)
            )
        
        # Adicionar bloco de informações do evento (reais ou mockadas)
        event_info_block = ""
        
        if self._mock_event_info is not None:
            # Modo mock: usar dados simulados
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
            
            event_info_block = (
                "\n\n[Dados simulados do evento para teste]\n"
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
        elif self._event_info is not None:
            # Modo real: usar informações reais do evento
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
            
            # Adicionar status de inscrições
            if 'status' in ei['tickets']:
                event_info_parts.append("")
                event_info_parts.append("Status de inscrições:")
                if 'message' in ei['tickets']['status']:
                    event_info_parts.append(f"- {ei['tickets']['status']['message']}")
                if 'note' in ei['tickets']['status']:
                    event_info_parts.append(f"- {ei['tickets']['status']['note']}")
            
            # Adicionar política de cancelamento
            if 'cancellation_policy' in ei['tickets']:
                event_info_parts.append("")
                event_info_parts.append("Política de cancelamento:")
                event_info_parts.append(f"- {ei['tickets']['cancellation_policy']}")
            
            # Adicionar processo de inscrição
            if 'registration_process' in ei['tickets']:
                event_info_parts.append("")
                event_info_parts.append("Processo de inscrição:")
                if 'description' in ei['tickets']['registration_process']:
                    event_info_parts.append(ei['tickets']['registration_process']['description'])
                if 'user_area_instructions' in ei['tickets']['registration_process']:
                    event_info_parts.append(f"Instrução: {ei['tickets']['registration_process']['user_area_instructions']}")
            
            # Adicionar recomendações para o bot
            if 'recommendation_for_bot' in ei['tickets']:
                event_info_parts.append("")
                event_info_parts.append("Recomendação: " + ei['tickets']['recommendation_for_bot'])
            
            # Adicionar informações sobre palestrantes
            if 'speakers_page' in ei:
                event_info_parts.append("")
                event_info_parts.append("Palestrantes:")
                event_info_parts.append(f"Página: {ei['speakers_page']['url']}")
                if 'note' in ei['speakers_page']:
                    event_info_parts.append(f"Nota: {ei['speakers_page']['note']}")
            
            # Adicionar informações do Comitê Técnico
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
            
            # Adicionar informações sobre patrocínio
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
            
            # Adicionar área do usuário
            if 'user_area' in ei:
                event_info_parts.append("")
                event_info_parts.append("Área do usuário:")
                event_info_parts.append(f"URL: {ei['user_area']['url']}")
                if 'features' in ei['user_area']:
                    event_info_parts.append("Funcionalidades:")
                    event_info_parts.extend([f"- {item}" for item in ei['user_area']['features']])
            
            event_info_block = (
                "\n\n[Informações do evento BioSummit 2026]\n"
                + "\n".join(event_info_parts)
            )
        
        if event_info_block:
            hybrid_system_prompt = hybrid_system_prompt + event_info_block
        
        logger.debug(
            f"Prompt híbrido construído: user_id={user_id}, "
            f"in_registration_flow={flow_hint.in_registration_flow}, "
            f"current_field={flow_hint.current_field}, "
            f"field_captured={flow_hint.field_captured}, "
            f"event_info_loaded={self._event_info is not None}, mock_enabled={self._mock_event_info is not None}"
        )

        # 4. Construir contexto (histórico recente)
        history_messages = state.get_recent_messages(self._config.max_history_turns)

        # 5. Adicionar mensagem atual do usuário na fila de envio
        messages_for_model = history_messages + [
            Message(role=Role.USER, content=message_text)
        ]

        # 6. Chamar modelo de linguagem SEMPRE
        logger.debug(
            f"Mensagem será encaminhada para modelo de linguagem: user_id={user_id}, "
            f"history_size={len(state.history)}"
        )
        
        reply_text = self._lm_client.generate_reply(
            system_prompt=hybrid_system_prompt,
            messages=messages_for_model,
        )

        logger.info(
            f"Resposta obtida da OpenAI: user_id={user_id}, "
            f"history_turns={len(state.history)}, "
            f"reply_length={len(reply_text)}, "
            f"in_registration_flow={flow_hint.in_registration_flow}"
        )
        logger.debug(
            f"Resposta da OpenAI (preview): user_id={user_id}, "
            f"reply_preview={reply_text[:100]}..."
        )

        # 7. Atualizar estado da conversa
        state.add_turn(user_msg=message_text, assistant_msg=reply_text)

        # 8. Retornar resposta com metadados mínimos
        return {
            "user_id": user_id,
            "reply": reply_text,
            "turns": len(state.history),
        }

