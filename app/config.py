from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    """
    Configurações principais da aplicação.

    Segue a ideia de centralizar parâmetros críticos
    para facilitar revisão, testes e mudanças futuras.
    """
    openai_api_key: str
    openai_model: str = "gpt-3o-mini"
    database_url: str = "sqlite:///./biosummit.db"
    smtp_host: str = "dev-log"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "inscricao@biosummit.com.br"
    bot_api_key: str = ""
    mock_event_data: bool = False
    system_prompt: str = (
        """
        Você é o assistente oficial do BioSummit 2026.

        ### Comportamento e diretrizes:

        - Use as informações do evento fornecidas no bloco [Informações do evento BioSummit 2026] para responder perguntas sobre o evento.
        - Responda sempre de forma clara, objetiva e educada.
        - Nunca invente informações que não estejam no bloco de informações do evento.
        - Se uma informação não estiver disponível no bloco de informações, diga: "Não tenho essa informação no momento. Posso encaminhar sua dúvida para a organização."
        - Sempre ofereça encaminhamento para a organização quando for algo muito específico ou não disponível.
        - IMPORTANTE: Sempre responda no mesmo idioma em que a mensagem foi escrita. Se o usuário escrever em inglês, responda em inglês. Se escrever em espanhol, responda em espanhol. Se escrever em português, responda em português. Detecte automaticamente o idioma da mensagem e mantenha a conversa nesse idioma.

        ### Sobre o fluxo de inscrição:
        - Você receberá, às vezes, um contexto adicional de fluxo de inscrição em um bloco chamado [Contexto do fluxo de inscrição].
        - Sempre respeite essas instruções, mantendo um tom natural e humano.
        - Integre as instruções do fluxo de inscrição de forma suave na conversa, sem parecer robótico.
        - Quando estiver no fluxo de inscrição, pode responder dúvidas sobre o evento, mas sempre retome suavemente ao próximo passo necessário.

        """
    )
    max_history_turns: int = 10  # quantos turnos manter no contexto

    @classmethod
    def load_from_env(cls) -> "AppConfig":
        """
        Carrega configuração a partir de variáveis de ambiente.
        Primeiro tenta carregar do arquivo .env, depois do ambiente do sistema.
        Levanta erro explícito se algo crítico faltar.
        """
        # Carrega variáveis do arquivo .env se existir
        load_dotenv()
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Variável de ambiente OPENAI_API_KEY não definida.")

        model = os.getenv("OPENAI_MODEL", "gpt-3o-mini")
        database_url = os.getenv("DATABASE_URL", "sqlite:///./biosummit.db")
        smtp_host = os.getenv("SMTP_HOST", "dev-log")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        smtp_from = os.getenv("SMTP_FROM", "inscricao@biosummit.com.br")
        bot_api_key = os.getenv("BOT_API_KEY", "")
        
        # Carregar flag de mock de dados do evento
        mock_event_data_raw = os.getenv("BIOSUMMIT_MOCK_EVENT_DATA", "0").lower()
        mock_event_data = mock_event_data_raw in ("1", "true", "yes", "y")
        return cls(
            openai_api_key=api_key,
            openai_model=model,
            database_url=database_url,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            smtp_from=smtp_from,
            bot_api_key=bot_api_key,
            mock_event_data=mock_event_data,
        )

