from enum import Enum
from pydantic import BaseModel, ConfigDict


class Role(str, Enum): # só aceita estes 3 valores
    CAMPUS_USER = "CAMPUS_USER"
    TECHNICIAN = "TECHNICIAN"
    ADMIN = "ADMIN"


class UserCreate(BaseModel):  # o que o cliente ENVIA no POST
    name: str
    email: str
    role: Role = Role.CAMPUS_USER # se não enviar, assume CAMPUS_USER


class UserOut(BaseModel): # o que o serviço DEVOLVE
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: Role