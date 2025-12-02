import logging
from typing import Tuple
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .session_manager import ConversationState
from .registration_state import RegistrationStep, RegistrationData
from .normalizers import normalize_phone, normalize_cpf, normalize_city_state, normalize_profile, UF_MAP
from ..storage.repository import ParticipantRepository
from ..infra.email_service import EmailService

logger = logging.getLogger(__name__)


class RegistrationManager:
    """
    Gerencia o fluxo de inscrição no evento.
    
    Implementa uma máquina de estados para conduzir o usuário
    através do processo de cadastro passo a passo.
    """

    def __init__(
        self,
        db_session_factory: sessionmaker,
        email_service: EmailService,
    ) -> None:
        self._db_session_factory = db_session_factory
        self._email_service = email_service

    def _detect_registration_intent(self, text: str) -> bool:
        """
        Detecta se o usuário quer se inscrever no evento.
        """
        text_lower = text.lower()
        keywords = [
            "inscrever",
            "inscrição",
            "inscricao",
            "inscriçao",
            "inscricão",
            "inscrever-me",
            "quero participar",
            "como participar",
            "quero ir",
            "fazer inscrição",
            "me inscrever",
            "cadastrar",
            "cadastro",
        ]
        return any(keyword in text_lower for keyword in keywords)

    def _is_valid_email(self, email: str) -> bool:
        """
        Validação simples de e-mail.
        """
        return "@" in email and "." in email.split("@")[1]

    def handle_message(
        self,
        state: ConversationState,
        user_text: str,
    ) -> Tuple[ConversationState, str]:
        """
        Processa mensagem do usuário no contexto do fluxo de inscrição.
        
        Retorna (estado_atualizado, resposta_do_bot).
        Se resposta_do_bot for vazia, significa que não é parte do fluxo de inscrição.
        """
        step = state.registration_step
        data = state.registration_data

        # 1. IDLE: detectar intenção de inscrição
        if step == RegistrationStep.IDLE:
            if self._detect_registration_intent(user_text):
                logger.info(
                    f"Usuário iniciou fluxo de inscrição: user_id={state.user_id}"
                )
                state.registration_step = RegistrationStep.ASKING_NAME
                return (
                    state,
                    "Perfeito! Vamos fazer sua inscrição no BioSummit 2026.\n"
                    "Para começar, por favor, me informe seu nome completo.",
                )
            return (state, "")

        # 2. ASKING_NAME: coletar nome completo
        if step == RegistrationStep.ASKING_NAME:
            if user_text.strip():
                data.full_name = user_text.strip()
                logger.debug(
                    f"Nome coletado: user_id={state.user_id}, "
                    f"name={data.full_name}"
                )
                state.registration_step = RegistrationStep.ASKING_EMAIL
                return (
                    state,
                    "Agora, por favor, me informe seu e-mail principal.",
                )
            return (
                state,
                "Por favor, informe seu nome completo para continuarmos.",
            )

        # 3. ASKING_EMAIL: coletar e validar e-mail
        if step == RegistrationStep.ASKING_EMAIL:
            email = user_text.strip()
            if self._is_valid_email(email):
                data.email = email
                logger.debug(
                    f"E-mail coletado: user_id={state.user_id}, "
                    f"email={email}"
                )
                state.registration_step = RegistrationStep.ASKING_CPF
                return (
                    state,
                    "Agora, por favor, me informe seu CPF (apenas números).",
                )
            logger.warning(
                f"E-mail inválido recebido: user_id={state.user_id}, "
                f"email_input={email[:50]}"
            )
            return (
                state,
                "E-mail inválido. Por favor, informe um e-mail válido (exemplo: seu.nome@email.com).",
            )

        # 3.5. ASKING_CPF: coletar e validar CPF
        if step == RegistrationStep.ASKING_CPF:
            normalized_cpf = normalize_cpf(user_text)
            if not normalized_cpf:
                logger.warning(
                    f"CPF inválido recebido: user_id={state.user_id}, "
                    f"cpf_input={user_text[:30]}"
                )
                return (
                    state,
                    "CPF inválido. Por favor, informe seu CPF com 11 dígitos (apenas números ou no formato 123.456.789-10).",
                )
            
            # Verificar se CPF já está cadastrado
            db_session: Session = self._db_session_factory()
            try:
                repo = ParticipantRepository(db_session)
                existing = repo.find_by_cpf(normalized_cpf)
                
                if existing:
                    logger.warning(
                        f"Tentativa de inscrição com CPF já cadastrado: "
                        f"user_id={state.user_id}, cpf={normalized_cpf}, "
                        f"existing_name={existing.full_name}"
                    )
                    # Resetar o fluxo de inscrição
                    state.registration_step = RegistrationStep.IDLE
                    state.registration_data = RegistrationData()
                    return (
                        state,
                        f"Este CPF já está cadastrado no sistema.\n"
                        f"Nome cadastrado: {existing.full_name}\n"
                        f"E-mail: {existing.email}\n\n"
                        f"Se você acredita que isso é um erro, entre em contato com a organização do evento.",
                    )
                
                # CPF válido e não cadastrado
                data.cpf = normalized_cpf
                logger.debug(
                    f"CPF coletado e validado: user_id={state.user_id}, cpf={normalized_cpf}"
                )
                state.registration_step = RegistrationStep.ASKING_PHONE
                return (
                    state,
                    "Ótimo! Agora, por favor, me informe seu telefone com DDD.",
                )
            finally:
                db_session.close()

        # 4. ASKING_PHONE: coletar telefone
        if step == RegistrationStep.ASKING_PHONE:
            parsed_phone = normalize_phone(user_text)
            if not parsed_phone:
                logger.warning(
                    f"Telefone inválido recebido: user_id={state.user_id}, "
                    f"phone_input={user_text[:30]}"
                )
                return (
                    state,
                    "Não consegui entender seu telefone. "
                    "Envie no formato com DDD, por exemplo: 41999999999.",
                )
            data.phone = parsed_phone
            logger.debug(
                f"Telefone normalizado: user_id={state.user_id}, "
                f"phone={parsed_phone}"
            )
            state.registration_step = RegistrationStep.ASKING_CITY
            return (
                state,
                "Agora, por favor, me informe sua cidade.",
            )

        # 5. ASKING_CITY: coletar cidade (pode vir com UF junto)
        if step == RegistrationStep.ASKING_CITY:
            if not user_text.strip():
                return (
                    state,
                    "Por favor, informe sua cidade para continuarmos.",
                )
            
            city, uf = normalize_city_state(user_text)
            
            if not city:
                logger.warning(
                    f"Cidade não identificada: user_id={state.user_id}, "
                    f"input={user_text[:50]}"
                )
                return (
                    state,
                    "Não consegui entender sua cidade. Por favor, informe o nome da sua cidade.",
                )
            
            data.city = city
            logger.debug(
                f"Cidade coletada: user_id={state.user_id}, "
                f"city={city}, uf={uf or 'não informado'}"
            )
            
            # Se já veio com UF, pula o passo de estado
            if uf:
                data.state = uf
                state.registration_step = RegistrationStep.ASKING_PROFILE
                return (
                    state,
                    "Por último, qual é o seu perfil?\n"
                    "(Exemplos: Produtor rural, Pesquisador(a), Empresa/Expositor, Estudante, etc.)",
                )
            else:
                state.registration_step = RegistrationStep.ASKING_STATE
                return (
                    state,
                    "Agora, por favor, me informe seu estado (UF).",
                )

        # 6. ASKING_STATE: coletar estado (UF)
        if step == RegistrationStep.ASKING_STATE:
            if not user_text.strip():
                return (
                    state,
                    "Por favor, informe seu estado (UF) para continuarmos.",
                )
            
            # Tenta normalizar (pode vir "Paraná" ou "PR")
            _, uf = normalize_city_state(user_text)
            
            # Se não conseguiu normalizar, tenta pegar as últimas 2 letras
            if not uf:
                text_upper = user_text.strip().upper()
                if len(text_upper) == 2 and text_upper in UF_MAP:
                    uf = text_upper
                else:
                    # Tenta extrair UF de frases como "sou do Paraná"
                    words = text_upper.split()
                    for word in words:
                        if len(word) == 2 and word in UF_MAP:
                            uf = word
                            break
            
            if not uf:
                logger.warning(
                    f"Estado (UF) não identificado: user_id={state.user_id}, "
                    f"input={user_text[:50]}"
                )
                return (
                    state,
                    "Não consegui entender seu estado. "
                    "Por favor, informe a sigla do estado (UF), por exemplo: PR, SP, MG.",
                )
            
            data.state = uf
            logger.debug(
                f"Estado coletado: user_id={state.user_id}, "
                f"state={uf}"
            )
            state.registration_step = RegistrationStep.ASKING_PROFILE
            return (
                state,
                "Por último, qual é o seu perfil?\n"
                "(Exemplos: Produtor rural, Pesquisador(a), Empresa/Expositor, Estudante, etc.)",
            )

        # 7. ASKING_PROFILE: coletar perfil
        if step == RegistrationStep.ASKING_PROFILE:
            if not user_text.strip():
                return (
                    state,
                    "Por favor, informe seu perfil para continuarmos.",
                )
            
            data.profile = normalize_profile(user_text)
            logger.debug(
                f"Perfil normalizado: user_id={state.user_id}, "
                f"profile={data.profile}"
            )
            state.registration_step = RegistrationStep.CONFIRMING
            
            # Montar resumo com dados normalizados
            summary = f"""Confira seus dados:

Nome: {data.full_name}
E-mail: {data.email}
CPF: {data.cpf or 'Não informado'}
Telefone: {data.phone or 'Não informado'}
Cidade/UF: {data.city or 'Não informado'}/{data.state or 'Não informado'}
Perfil: {data.profile or 'Não informado'}

Está tudo correto? Responda 'sim' para confirmar ou 'não' para reiniciar o cadastro."""
            
            return (state, summary)

        # 8. CONFIRMING: confirmar ou reiniciar
        if step == RegistrationStep.CONFIRMING:
            response_lower = user_text.strip().lower()
            
            if response_lower.startswith("sim"):
                logger.info(
                    f"Inscrição será confirmada: user_id={state.user_id}, "
                    f"email={data.email}, cpf={data.cpf}"
                )
                
                # Verificar novamente se CPF já está cadastrado (verificação dupla)
                db_session: Session = self._db_session_factory()
                try:
                    repo = ParticipantRepository(db_session)
                    
                    if data.cpf:
                        existing = repo.find_by_cpf(data.cpf)
                        if existing:
                            logger.warning(
                                f"CPF já cadastrado no momento da confirmação: "
                                f"user_id={state.user_id}, cpf={data.cpf}, "
                                f"existing_name={existing.full_name}"
                            )
                            # Resetar o fluxo
                            state.registration_step = RegistrationStep.IDLE
                            state.registration_data = RegistrationData()
                            return (
                                state,
                                f"Este CPF já está cadastrado no sistema.\n"
                                f"Nome cadastrado: {existing.full_name}\n"
                                f"E-mail: {existing.email}\n\n"
                                f"Se você acredita que isso é um erro, entre em contato com a organização do evento.",
                            )
                    
                    # Salvar no banco de dados
                    participant = repo.create_participant(
                        full_name=data.full_name or "",
                        email=data.email or "",
                        cpf=data.cpf or "",
                        phone=data.phone,
                        city=data.city,
                        state=data.state,
                        profile=data.profile,
                    )
                    
                    # ASSERT: garantir que o participante foi persistido com ID
                    assert participant.id is not None, (
                        f"Participant persisted without id! "
                        f"This indicates a persistence error. "
                        f"user_id={state.user_id}, email={data.email}"
                    )
                    
                    logger.info(
                        f"Participante criado no banco: "
                        f"id={participant.id}, name={participant.full_name}, "
                        f"email={participant.email}"
                    )
                    
                    # Enviar e-mail de confirmação
                    if data.email and data.full_name:
                        try:
                            self._email_service.send_registration_confirmation(
                                to_email=data.email,
                                full_name=data.full_name,
                            )
                            # O EmailService já loga internamente se foi enviado ou apenas simulado
                            # Este log adicional confirma que o processo foi concluído
                            logger.debug(
                                f"Processo de envio de e-mail concluído: to={data.email}"
                            )
                        except Exception as email_error:
                            logger.error(
                                f"Falha ao enviar e-mail de confirmação: "
                                f"to={data.email}, error={type(email_error).__name__}: {email_error}",
                                exc_info=True,
                            )
                            # Não interrompe o fluxo, mas loga o erro
                            # O usuário já foi registrado no banco
                    
                    state.registration_step = RegistrationStep.COMPLETED
                    return (
                        state,
                        "Sua inscrição foi registrada com sucesso! 🎟️\n"
                        "Você receberá um e-mail de confirmação em breve.\n"
                        "Se precisar de mais alguma coisa sobre o BioSummit 2026, é só me chamar.",
                    )
                except IntegrityError as db_error:
                    error_msg = str(db_error).lower()
                    
                    # Verificar se é erro de CPF duplicado
                    if "cpf" in error_msg or "unique constraint" in error_msg or "duplicate" in error_msg:
                        logger.warning(
                            f"CPF duplicado detectado via IntegrityError: user_id={state.user_id}, "
                            f"cpf={data.cpf}, error={type(db_error).__name__}"
                        )
                        db_session.rollback()
                        
                        # Resetar o fluxo e informar usuário
                        state.registration_step = RegistrationStep.IDLE
                        state.registration_data = RegistrationData()
                        
                        # Tentar buscar o participante existente para mostrar informações
                        try:
                            existing = repo.find_by_cpf(data.cpf or "")
                            if existing:
                                return (
                                    state,
                                    f"Este CPF já está cadastrado no sistema.\n"
                                    f"Nome cadastrado: {existing.full_name}\n"
                                    f"E-mail: {existing.email}\n\n"
                                    f"Se você acredita que isso é um erro, entre em contato com a organização do evento.",
                                )
                        except:
                            pass
                        
                        return (
                            state,
                            "Este CPF já está cadastrado no sistema. "
                            "Se você acredita que isso é um erro, entre em contato com a organização do evento.",
                        )
                    
                    logger.error(
                        f"Erro de integridade ao persistir participante no banco: "
                        f"user_id={state.user_id}, email={data.email}, cpf={data.cpf}, "
                        f"error={type(db_error).__name__}: {db_error}",
                        exc_info=True,
                    )
                    db_session.rollback()
                    raise
                except SQLAlchemyError as db_error:
                    logger.error(
                        f"Erro ao persistir participante no banco: "
                        f"user_id={state.user_id}, email={data.email}, "
                        f"error={type(db_error).__name__}: {db_error}",
                        exc_info=True,
                    )
                    db_session.rollback()
                    raise
                except AssertionError as assert_error:
                    logger.error(
                        f"Assertion falhou ao persistir participante: "
                        f"user_id={state.user_id}, email={data.email}, "
                        f"error={assert_error}",
                        exc_info=True,
                    )
                    raise
                except Exception as e:
                    logger.error(
                        f"Erro inesperado ao processar inscrição: "
                        f"user_id={state.user_id}, email={data.email}, "
                        f"error={type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    raise
                finally:
                    db_session.close()
            
            elif response_lower.startswith("não") or response_lower.startswith("nao"):
                # Reiniciar cadastro
                state.registration_data = RegistrationData()
                state.registration_step = RegistrationStep.ASKING_NAME
                return (
                    state,
                    "Sem problemas! Vamos começar novamente.\n"
                    "Por favor, me informe seu nome completo.",
                )
            
            else:
                return (
                    state,
                    "Por favor, responda apenas 'sim' para confirmar ou 'não' para reiniciar o cadastro.",
                )

        # 9. COMPLETED: não interfere no fluxo normal
        if step == RegistrationStep.COMPLETED:
            return (state, "")

        # Fallback (não deveria chegar aqui)
        return (state, "")

