import logging
import smtplib
import ssl
from email.message import EmailMessage
from smtplib import SMTPException, SMTPServerDisconnected
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
            logger.warning(
                f"⚠️ MODO DEV: E-mail NÃO foi enviado (apenas simulado). "
                f"Para enviar e-mails reais, configure SMTP_HOST no .env. "
                f"Destinatário: {to_email}"
            )
            logger.info(
                f"E-mail de confirmação (FAKE) logado para destinatário: {to_email}"
            )
            print("\n" + "=" * 60)
            print("📧 E-MAIL DE CONFIRMAÇÃO (DEV MODE - NÃO ENVIADO)")
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
                    f"port={self._config.smtp_port}, from={self._config.smtp_from}"
                )
                
                # Criar contexto SSL padrão
                ssl_context = ssl.create_default_context()
                
                email_sent = False
                last_error = None
                
                # Tentar porta 465 primeiro (SSL direto)
                if self._config.smtp_port == 465:
                    logger.debug("Tentando porta 465 com SMTP_SSL (SSL direto)")
                    try:
                        server = smtplib.SMTP_SSL(
                            self._config.smtp_host, 
                            self._config.smtp_port,
                            timeout=30,
                            context=ssl_context
                        )
                        server.set_debuglevel(0)
                        
                        if self._config.smtp_user:
                            logger.debug(f"Autenticando SMTP: user={self._config.smtp_user}")
                            server.login(self._config.smtp_user, self._config.smtp_password)
                        
                        logger.debug(f"Enviando mensagem SMTP para: {to_email}")
                        server.send_message(msg)
                        server.quit()
                        email_sent = True
                        
                    except (SMTPServerDisconnected, ConnectionError, Exception) as e:
                        last_error = e
                        logger.warning(
                            f"Porta 465 falhou: {type(e).__name__}: {e}. "
                            f"Tentando porta 587 com STARTTLS como fallback..."
                        )
                        # Tentar porta 587 como fallback
                        try:
                            logger.debug("Tentando porta 587 com STARTTLS como fallback")
                            server = smtplib.SMTP(
                                self._config.smtp_host, 
                                587,
                                timeout=30
                            )
                            server.set_debuglevel(0)
                            
                            if self._config.smtp_user:
                                server.starttls(context=ssl_context)
                                server.login(self._config.smtp_user, self._config.smtp_password)
                            
                            server.send_message(msg)
                            server.quit()
                            email_sent = True
                            logger.info("Email enviado com sucesso usando porta 587 (fallback)")
                            
                        except Exception as e2:
                            last_error = e2
                            logger.error(f"Porta 587 também falhou: {type(e2).__name__}: {e2}")
                
                else:
                    # STARTTLS (porta 587 ou outras)
                    logger.debug("Usando SMTP com STARTTLS")
                    server = smtplib.SMTP(
                        self._config.smtp_host, 
                        self._config.smtp_port,
                        timeout=30
                    )
                    server.set_debuglevel(0)
                    
                    if self._config.smtp_user:
                        logger.debug(f"Autenticando SMTP: user={self._config.smtp_user}")
                        server.starttls(context=ssl_context)
                        server.login(self._config.smtp_user, self._config.smtp_password)
                    
                    logger.debug(f"Enviando mensagem SMTP para: {to_email}")
                    server.send_message(msg)
                    server.quit()
                    email_sent = True
                
                if not email_sent and last_error:
                    raise last_error
                
                logger.info(
                    f"✅ E-mail REAL enviado com sucesso via SMTP: to={to_email}, "
                    f"host={self._config.smtp_host}, port={self._config.smtp_port}"
                )
            except SMTPException as e:
                error_type = type(e).__name__
                error_msg = str(e)
                
                # Mensagem mais detalhada para erros comuns
                if "Connection unexpectedly closed" in error_msg or isinstance(e, SMTPServerDisconnected):
                    logger.error(
                        f"Erro SMTP: Conexão fechada durante autenticação. "
                        f"Verifique: host={self._config.smtp_host}, port={self._config.smtp_port}, "
                        f"user={self._config.smtp_user}, "
                        f"Possíveis causas: credenciais incorretas, porta errada, ou servidor bloqueando conexão."
                    )
                else:
                    logger.error(
                        f"Erro SMTP ao enviar e-mail: to={to_email}, "
                        f"error={error_type}: {error_msg}",
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

