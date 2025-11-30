from typing import Tuple
from sqlalchemy.orm import sessionmaker, Session
from .session_manager import ConversationState
from .registration_state import RegistrationStep, RegistrationData
from .normalizers import normalize_phone, normalize_city_state, normalize_profile, UF_MAP
from ..storage.repository import ParticipantRepository
from ..infra.email_service import EmailService


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
                state.registration_step = RegistrationStep.ASKING_PHONE
                return (
                    state,
                    "Ótimo! Agora, por favor, me informe seu telefone com DDD.",
                )
            return (
                state,
                "E-mail inválido. Por favor, informe um e-mail válido (exemplo: seu.nome@email.com).",
            )

        # 4. ASKING_PHONE: coletar telefone
        if step == RegistrationStep.ASKING_PHONE:
            parsed_phone = normalize_phone(user_text)
            if not parsed_phone:
                return (
                    state,
                    "Não consegui entender seu telefone. "
                    "Envie no formato com DDD, por exemplo: 41999999999.",
                )
            data.phone = parsed_phone
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
                return (
                    state,
                    "Não consegui entender sua cidade. Por favor, informe o nome da sua cidade.",
                )
            
            data.city = city
            
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
                return (
                    state,
                    "Não consegui entender seu estado. "
                    "Por favor, informe a sigla do estado (UF), por exemplo: PR, SP, MG.",
                )
            
            data.state = uf
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
            state.registration_step = RegistrationStep.CONFIRMING
            
            # Montar resumo com dados normalizados
            summary = f"""Confira seus dados:

Nome: {data.full_name}
E-mail: {data.email}
Telefone: {data.phone or 'Não informado'}
Cidade/UF: {data.city or 'Não informado'}/{data.state or 'Não informado'}
Perfil: {data.profile or 'Não informado'}

Está tudo correto? Responda 'sim' para confirmar ou 'não' para reiniciar o cadastro."""
            
            return (state, summary)

        # 8. CONFIRMING: confirmar ou reiniciar
        if step == RegistrationStep.CONFIRMING:
            response_lower = user_text.strip().lower()
            
            if response_lower.startswith("sim"):
                # Salvar no banco de dados
                db_session: Session = self._db_session_factory()
                try:
                    repo = ParticipantRepository(db_session)
                    repo.create_participant(
                        full_name=data.full_name or "",
                        email=data.email or "",
                        phone=data.phone,
                        city=data.city,
                        state=data.state,
                        profile=data.profile,
                    )
                    
                    # Enviar e-mail de confirmação
                    if data.email and data.full_name:
                        self._email_service.send_registration_confirmation(
                            to_email=data.email,
                            full_name=data.full_name,
                        )
                    
                    state.registration_step = RegistrationStep.COMPLETED
                    return (
                        state,
                        "Sua inscrição foi registrada com sucesso! 🎟️\n"
                        "Você receberá um e-mail de confirmação em breve.\n"
                        "Se precisar de mais alguma coisa sobre o BioSummit 2026, é só me chamar.",
                    )
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

