from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .database import Base


class Participant(Base):
    """
    Modelo de participante do evento.
    """
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    profile = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

