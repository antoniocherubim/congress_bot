import smtplib
from email.message import EmailMessage
from ..config import AppConfig


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
        subject = "Confirmação de inscrição - BioSummit 2026"
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
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                if self._config.smtp_user:
                    server.starttls()
                    server.login(self._config.smtp_user, self._config.smtp_password)
                server.send_message(msg)

