import logging
import smtplib
from email.message import EmailMessage
from smtplib import SMTPException
from ..config import AppConfig

logger = logging.getLogger(__name__)


class EmailService:
    """
    Serviço para envio de e-mails.
    Em desenvolvimento, apenas loga no console.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def send_registration_confirmation(self, to_email: str, full_name: str) -> None:
        """
        Envia e-mail de confirmação de inscrição.
        """
        # ASSERT: garantir que dados básicos estão presentes
        if not to_email or not to_email.strip():
            logger.error(
                f"Tentativa de envio de e-mail sem destinatário: full_name={full_name}"
            )
            raise ValueError("to_email não pode estar vazio")
        
        if not full_name or not full_name.strip():
            logger.error(
                f"Tentativa de envio de e-mail sem nome: to_email={to_email}"
            )
            raise ValueError("full_name não pode estar vazio")
        
        subject = "Confirmação de inscrição - BioSummit 2026"
        logger.debug(
            f"Montando e-mail de confirmação: to={to_email}, subject={subject}"
        )
        
        body = f"""Olá, {full_name}!

Sua inscrição no BioSummit 2026 foi confirmada com sucesso! 🎟️

Detalhes do evento:
- Data: 6 e 7 de maio de 2026
- Local: Expo Dom Pedro, Campinas – SP
- Tema: Bioinsumos e Agricultura Regenerativa: Cultivando o Futuro Sustentável

Em breve você receberá mais informações sobre a programação e próximos passos.

Aguardamos você no BioSummit 2026!

Equipe BioSummit
"""

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._config.smtp_from
        msg["To"] = to_email
        msg.set_content(body)

        if self._config.smtp_host == "dev-log":
            # Modo desenvolvimento: apenas logar
            logger.info(
                f"E-mail de confirmação (FAKE) logado para destinatário: {to_email}"
            )
            print("\n" + "=" * 60)
            print("📧 E-MAIL DE CONFIRMAÇÃO (DEV MODE)")
            print("=" * 60)
            print(f"De: {msg['From']}")
            print(f"Para: {msg['To']}")
            print(f"Assunto: {msg['Subject']}")
            print("-" * 60)
            print(msg.get_content())
            print("=" * 60 + "\n")
        else:
            # Modo produção: enviar via SMTP
            try:
                logger.info(
                    f"Iniciando conexão SMTP: host={self._config.smtp_host}, "
                    f"port={self._config.smtp_port}"
                )
                with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                    if self._config.smtp_user:
                        server.starttls()
                        server.login(self._config.smtp_user, self._config.smtp_password)
                    server.send_message(msg)
                logger.info(
                    f"E-mail enviado com sucesso: to={to_email}"
                )
            except SMTPException as e:
                logger.error(
                    f"Erro SMTP ao enviar e-mail: to={to_email}, "
                    f"error={type(e).__name__}: {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"Erro inesperado ao enviar e-mail: to={to_email}, "
                    f"error={type(e).__name__}: {e}",
                    exc_info=True,
                )
                raise

