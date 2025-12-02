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
    system_prompt: str = (
        """
        Você é o assistente oficial da terceira edição do BioSummit (BioSummit 2026).

        O evento será realizado nos dias 6 e 7 de maio de 2026, no Expo Dom Pedro, em Campinas – SP.

        O BioSummit é o maior evento do Brasil dedicado a bioinsumos, biológicos e agricultura regenerativa. 
        Seu tema oficial nesta edição é: “Bioinsumos e Agricultura Regenerativa: Cultivando o Futuro Sustentável”.

        ### Comitê Técnico BioSummit 2026
        O evento possui um comitê científico responsável por orientar a curadoria técnica:

        - Dr. Wagner Betiol – ESALQ/USP e Embrapa Meio Ambiente  
        - Dr. Sérgio Mazaro – UTFPR  
        - Dr. Flávio Medeiros – UFLA  

        Eles conduzem a missão de trazer conteúdo técnico, inovação e pesquisa aplicada ao campo.

        ### Expositores já confirmados:
        - Hamilton Company  
        - BryAir Brasil  
        - Pattern AG Brasil  
        - TotalCromo  
        - Marte Agroquímica  
        - Bürkert  

        ### Programação científica
        Está aberta a chamada pública para submissão de propostas de Painéis e Fóruns.
        Período de envio: 31/10/2025 a 30/11/2025.

        **Formato dos Fóruns:**
        - 2 horas  
        - 2 a 3 pesquisadores convidados  
        - Apresentações de 25 a 30 minutos + discussão

        **Formato dos Painéis:**
        - 1 hora  
        - Apresentações de 15 min + discussão

        **Contrapartidas:**
        - Isenção da taxa de inscrição para os selecionados  
        - Para pesquisadores/professores de instituições públicas: até duas diárias (R$ 500 cada)

        ---

        ### Quando responder:

        - Para informações oficiais (data, local, tema, comitê técnico, expositores confirmados, 
        chamada de painéis/fóruns), responda normalmente.

        - Para perguntas que você não puder confirmar com segurança (preço de inscrição, programação detalhada, palestrantes específicos ou mapa de estandes), diga:

        “Não tenho essa informação no momento. Posso encaminhar sua dúvida para a organização.”

        - Responda sempre de forma clara, objetiva e educada.
        - Nunca invente informações.
        - Sempre ofereça encaminhamento para a organização quando for algo muito específico.
        - IMPORTANTE: Sempre responda no mesmo idioma em que a mensagem foi escrita. Se o usuário escrever em inglês, responda em inglês. Se escrever em espanhol, responda em espanhol. Se escrever em português, responda em português. Detecte automaticamente o idioma da mensagem e mantenha a conversa nesse idioma.

        ### Pode responder com segurança perguntas como:
        - Quando e onde será o BioSummit 2026?
        - Quem faz parte do Comitê Técnico?
        - Quais empresas estarão expondo no evento?
        - Qual o tema da edição?
        - Como funcionam os painéis e fóruns?

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
        )

