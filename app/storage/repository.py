import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .models import Participant

logger = logging.getLogger(__name__)


class ParticipantRepository:
    """
    Repositório para operações de persistência de participantes.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_participant(
        self,
        full_name: str,
        email: str,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        profile: Optional[str] = None,
    ) -> Participant:
        """
        Cria um novo participante no banco de dados.
        """
        logger.debug(
            f"Criando participante: name={full_name}, email={email}, "
            f"city={city}, state={state}, profile={profile}"
        )
        
        try:
            participant = Participant(
                full_name=full_name,
                email=email,
                phone=phone,
                city=city,
                state=state,
                profile=profile,
            )
            self._db.add(participant)
            self._db.commit()
            self._db.refresh(participant)
            
            # ASSERT: garantir que o participante foi persistido com ID
            assert participant.id is not None, (
                "Participant persisted without id! "
                "This indicates a persistence error."
            )
            
            logger.debug(
                f"Participante criado com sucesso: id={participant.id}, email={participant.email}"
            )
            
            return participant
        except IntegrityError as e:
            logger.error(
                f"Erro de integridade ao criar participante: email={email}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True,
            )
            self._db.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Erro de banco de dados ao criar participante: email={email}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True,
            )
            self._db.rollback()
            raise

