import logging
from typing import Optional
from dataclasses import dataclass
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .session_manager import ConversationState
from .registration_state import RegistrationStep, RegistrationData
from .normalizers import normalize_phone, normalize_cpf, normalize_city_state, normalize_profile, UF_MAP
from ..storage.repository import ParticipantRepository
from ..infra.email_service import EmailService

logger = logging.getLogger(__name__)


@dataclass
class RegistrationFlowHint:
    """
    Representa o estado lógico do fluxo de inscrição após processar uma mensagem.
    Não é a resposta final ao usuário, é um "guia" para a camada de linguagem.
    """
    state: ConversationState
    # Mensagem de guia do fluxo, ex: "Estamos pedindo o e-mail", "Inscrição concluída", etc.
    instruction: Optional[str]
    # Se a mensagem atual aparentemente forneceu o valor esperado
    field_captured: bool
    # Nome do campo esperado (nome, email, telefone, cidade_uf, perfil, etc.)
    current_field: Optional[str]
    # Se o fluxo de inscrição ainda está ativo (ou se já concluiu)
    in_registration_flow: bool


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

    def _create_hint(
        self,
        state: ConversationState,
        instruction: Optional[str],
        field_captured: bool,
        current_field: Optional[str],
        in_registration_flow: bool,
    ) -> RegistrationFlowHint:
        """Método auxiliar para criar um RegistrationFlowHint."""
        return RegistrationFlowHint(
            state=state,
            instruction=instruction,
            field_captured=field_captured,
            current_field=current_field,
            in_registration_flow=in_registration_flow,
        )

    def handle_message(
        self,
        state: ConversationState,
        user_text: str,
    ) -> RegistrationFlowHint:
        """
        Processa mensagem do usuário no contexto do fluxo de inscrição.
        
        Retorna RegistrationFlowHint com o estado atualizado e instruções
        para a camada de linguagem gerar a resposta final.
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
                return self._create_hint(
                    state=state,
                    instruction="O usuário iniciou o fluxo de inscrição. Estamos coletando o nome completo do participante.",
                    field_captured=False,
                    current_field="nome",
                    in_registration_flow=True,
                )
            return self._create_hint(
                state=state,
                instruction=None,
                field_captured=False,
                current_field=None,
                in_registration_flow=False,
            )

        # 2. ASKING_NAME: coletar nome completo
        if step == RegistrationStep.ASKING_NAME:
            if user_text.strip():
                data.full_name = user_text.strip()
                logger.debug(
                    f"Nome coletado: user_id={state.user_id}, "
                    f"name={data.full_name}"
                )
                state.registration_step = RegistrationStep.ASKING_EMAIL
                return self._create_hint(
                    state=state,
                    instruction="Nome confirmado. Agora precisamos do e-mail para contato.",
                    field_captured=True,
                    current_field="email",
                    in_registration_flow=True,
                )
            return self._create_hint(
                state=state,
                instruction="Faltam dados para concluir a inscrição. No momento esperamos o nome completo do participante.",
                field_captured=False,
                current_field="nome",
                in_registration_flow=True,
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
                return self._create_hint(
                    state=state,
                    instruction="E-mail confirmado. Agora precisamos do CPF (apenas números, 11 dígitos).",
                    field_captured=True,
                    current_field="cpf",
                    in_registration_flow=True,
                )
            logger.warning(
                f"E-mail inválido recebido: user_id={state.user_id}, "
                f"email_input={email[:50]}"
            )
            return self._create_hint(
                state=state,
                instruction="Faltam dados para concluir a inscrição. No momento esperamos um e-mail válido para contato.",
                field_captured=False,
                current_field="email",
                in_registration_flow=True,
            )

        # 3.5. ASKING_CPF: coletar e validar CPF
        if step == RegistrationStep.ASKING_CPF:
            normalized_cpf = normalize_cpf(user_text)
            if not normalized_cpf:
                logger.warning(
                    f"CPF inválido recebido: user_id={state.user_id}, "
                    f"cpf_input={user_text[:30]}"
                )
                return self._create_hint(
                    state=state,
                    instruction="Faltam dados para concluir a inscrição. No momento esperamos um CPF válido com 11 dígitos (apenas números ou no formato 123.456.789-10).",
                    field_captured=False,
                    current_field="cpf",
                    in_registration_flow=True,
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
                    return self._create_hint(
                        state=state,
                        instruction=f"Este CPF já está cadastrado no sistema. Nome cadastrado: {existing.full_name}. E-mail: {existing.email}. Se você acredita que isso é um erro, entre em contato com a organização do evento.",
                        field_captured=False,
                        current_field=None,
                        in_registration_flow=False,
                    )
                
                # CPF válido e não cadastrado
                data.cpf = normalized_cpf
                logger.debug(
                    f"CPF coletado e validado: user_id={state.user_id}, cpf={normalized_cpf}"
                )
                state.registration_step = RegistrationStep.ASKING_PHONE
                return self._create_hint(
                    state=state,
                    instruction="CPF confirmado. Agora precisamos do telefone com DDD para contato.",
                    field_captured=True,
                    current_field="telefone",
                    in_registration_flow=True,
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
                return self._create_hint(
                    state=state,
                    instruction="Faltam dados para concluir a inscrição. No momento esperamos um telefone válido com DDD (formato: 41999999999).",
                    field_captured=False,
                    current_field="telefone",
                    in_registration_flow=True,
                )
            data.phone = parsed_phone
            logger.debug(
                f"Telefone normalizado: user_id={state.user_id}, "
                f"phone={parsed_phone}"
            )
            state.registration_step = RegistrationStep.ASKING_CITY
            return self._create_hint(
                state=state,
                instruction="Telefone confirmado. Agora precisamos da cidade onde você mora.",
                field_captured=True,
                current_field="cidade",
                in_registration_flow=True,
            )

        # 5. ASKING_CITY: coletar cidade (pode vir com UF junto)
        if step == RegistrationStep.ASKING_CITY:
            if not user_text.strip():
                return self._create_hint(
                    state=state,
                    instruction="Faltam dados para concluir a inscrição. No momento esperamos o nome da sua cidade.",
                    field_captured=False,
                    current_field="cidade",
                    in_registration_flow=True,
                )
            
            city, uf = normalize_city_state(user_text)
            
            if not city:
                logger.warning(
                    f"Cidade não identificada: user_id={state.user_id}, "
                    f"input={user_text[:50]}"
                )
                return self._create_hint(
                    state=state,
                    instruction="Faltam dados para concluir a inscrição. No momento esperamos o nome da sua cidade.",
                    field_captured=False,
                    current_field="cidade",
                    in_registration_flow=True,
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
                return self._create_hint(
                    state=state,
                    instruction="Cidade e estado confirmados. Por último, precisamos saber qual é o seu perfil (exemplos: Produtor rural, Pesquisador(a), Empresa/Expositor, Estudante, etc.).",
                    field_captured=True,
                    current_field="perfil",
                    in_registration_flow=True,
                )
            else:
                state.registration_step = RegistrationStep.ASKING_STATE
                return self._create_hint(
                    state=state,
                    instruction="Cidade confirmada. Agora precisamos do estado (UF) onde você mora.",
                    field_captured=True,
                    current_field="estado",
                    in_registration_flow=True,
                )

        # 6. ASKING_STATE: coletar estado (UF)
        if step == RegistrationStep.ASKING_STATE:
            if not user_text.strip():
                return self._create_hint(
                    state=state,
                    instruction="Faltam dados para concluir a inscrição. No momento esperamos o estado (UF) onde você mora.",
                    field_captured=False,
                    current_field="estado",
                    in_registration_flow=True,
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
                return self._create_hint(
                    state=state,
                    instruction="Faltam dados para concluir a inscrição. No momento esperamos a sigla do estado (UF), por exemplo: PR, SP, MG.",
                    field_captured=False,
                    current_field="estado",
                    in_registration_flow=True,
                )
            
            data.state = uf
            logger.debug(
                f"Estado coletado: user_id={state.user_id}, "
                f"state={uf}"
            )
            state.registration_step = RegistrationStep.ASKING_PROFILE
            return self._create_hint(
                state=state,
                instruction="Estado confirmado. Por último, precisamos saber qual é o seu perfil (exemplos: Produtor rural, Pesquisador(a), Empresa/Expositor, Estudante, etc.).",
                field_captured=True,
                current_field="perfil",
                in_registration_flow=True,
            )

        # 7. ASKING_PROFILE: coletar perfil
        if step == RegistrationStep.ASKING_PROFILE:
            if not user_text.strip():
                return self._create_hint(
                    state=state,
                    instruction="Faltam dados para concluir a inscrição. No momento esperamos o perfil do participante (exemplos: Produtor rural, Pesquisador(a), Empresa/Expositor, Estudante, etc.).",
                    field_captured=False,
                    current_field="perfil",
                    in_registration_flow=True,
                )
            
            data.profile = normalize_profile(user_text)
            logger.debug(
                f"Perfil normalizado: user_id={state.user_id}, "
                f"profile={data.profile}"
            )
            state.registration_step = RegistrationStep.CONFIRMING
            
            # Montar resumo com dados normalizados para a IA
            summary_parts = [
                f"Nome: {data.full_name}",
                f"E-mail: {data.email}",
                f"CPF: {data.cpf or 'Não informado'}",
                f"Telefone: {data.phone or 'Não informado'}",
                f"Cidade/UF: {data.city or 'Não informado'}/{data.state or 'Não informado'}",
                f"Perfil: {data.profile or 'Não informado'}",
            ]
            
            return self._create_hint(
                state=state,
                instruction=f"Todos os dados foram coletados. Confira os dados coletados: {'; '.join(summary_parts)}. Peça para o usuário confirmar se está tudo correto, respondendo 'sim' para confirmar ou 'não' para reiniciar o cadastro.",
                field_captured=True,
                current_field="confirmacao",
                in_registration_flow=True,
            )

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
                            return self._create_hint(
                                state=state,
                                instruction=f"Este CPF já está cadastrado no sistema. Nome cadastrado: {existing.full_name}. E-mail: {existing.email}. Se você acredita que isso é um erro, entre em contato com a organização do evento.",
                                field_captured=False,
                                current_field=None,
                                in_registration_flow=False,
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
                    return self._create_hint(
                        state=state,
                        instruction="Inscrição concluída com sucesso. O participante foi registrado no banco de dados e receberá um e-mail de confirmação em breve. Agora o bot pode funcionar apenas como FAQ do evento.",
                        field_captured=True,
                        current_field=None,
                        in_registration_flow=False,
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
                                return self._create_hint(
                                    state=state,
                                    instruction=f"Este CPF já está cadastrado no sistema. Nome cadastrado: {existing.full_name}. E-mail: {existing.email}. Se você acredita que isso é um erro, entre em contato com a organização do evento.",
                                    field_captured=False,
                                    current_field=None,
                                    in_registration_flow=False,
                                )
                        except:
                            pass
                        
                        return self._create_hint(
                            state=state,
                            instruction="Este CPF já está cadastrado no sistema. Se você acredita que isso é um erro, entre em contato com a organização do evento.",
                            field_captured=False,
                            current_field=None,
                            in_registration_flow=False,
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
                return self._create_hint(
                    state=state,
                    instruction="O usuário pediu para reiniciar o cadastro. Vamos começar novamente coletando o nome completo do participante.",
                    field_captured=False,
                    current_field="nome",
                    in_registration_flow=True,
                )
            
            else:
                return self._create_hint(
                    state=state,
                    instruction="Faltam dados para concluir a inscrição. No momento esperamos a confirmação do usuário. O usuário deve responder 'sim' para confirmar ou 'não' para reiniciar o cadastro.",
                    field_captured=False,
                    current_field="confirmacao",
                    in_registration_flow=True,
                )

        # 9. COMPLETED: não interfere no fluxo normal
        if step == RegistrationStep.COMPLETED:
            return self._create_hint(
                state=state,
                instruction=None,
                field_captured=False,
                current_field=None,
                in_registration_flow=False,
            )

        # Fallback (não deveria chegar aqui)
        return self._create_hint(
            state=state,
            instruction=None,
            field_captured=False,
            current_field=None,
            in_registration_flow=False,
        )

