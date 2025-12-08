import logging
from typing import Dict, Any, Optional
from .session_manager import InMemorySessionManager
from .models import Message, Role
from .registration_manager import RegistrationManager, RegistrationFlowHint
from ..config import AppConfig
from ..infra.openai_client import LanguageModelClient
from ..infra.email_service import EmailService
from ..storage.database import create_session_factory
from ..domain.event_info import get_mock_event_info, EventInfo

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
        
        # Carregar dados mock do evento se habilitado
        self._mock_event_info: Optional[EventInfo] = None
        if config.mock_event_data:
            self._mock_event_info = get_mock_event_info()
            logger.info("Mock de dados do evento habilitado (BIOSUMMIT_MOCK_EVENT_DATA=True).")
        
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
        
        # Adicionar bloco de dados mock do evento se habilitado
        mock_event_block = ""
        if self._mock_event_info is not None:
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
            
            mock_event_block = (
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
        
        if mock_event_block:
            hybrid_system_prompt = hybrid_system_prompt + mock_event_block
        
        logger.debug(
            f"Prompt híbrido construído: user_id={user_id}, "
            f"in_registration_flow={flow_hint.in_registration_flow}, "
            f"current_field={flow_hint.current_field}, "
            f"field_captured={flow_hint.field_captured}, "
            f"mock_enabled={self._mock_event_info is not None}"
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

