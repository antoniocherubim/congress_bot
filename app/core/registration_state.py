from enum import Enum
from dataclasses import dataclass
from typing import Optional


class RegistrationStep(str, Enum):
    """
    Estados do fluxo de inscrição.
    """
    IDLE = "idle"
    ASKING_NAME = "asking_name"
    ASKING_EMAIL = "asking_email"
    ASKING_CPF = "asking_cpf"
    ASKING_PHONE = "asking_phone"
    ASKING_CITY = "asking_city"
    ASKING_STATE = "asking_state"
    ASKING_PROFILE = "asking_profile"
    CONFIRMING = "confirming"
    COMPLETED = "completed"


@dataclass
class RegistrationData:
    """
    Dados coletados durante o fluxo de inscrição.
    """
    full_name: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    profile: Optional[str] = None

