from typing import Optional
from sqlalchemy.orm import Session
from .models import Participant


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
        return participant

