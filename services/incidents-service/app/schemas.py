"""Formatos de entrada e saída da API (JSON em camelCase, tal como nos eventos)."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.state_machine import Status


class Priority(str, Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


class Category(str, Enum):
    ELETRICO = "ELETRICO"
    REDE = "REDE"
    EQUIPAMENTO = "EQUIPAMENTO"
    SALA = "SALA"
    LIMPEZA = "LIMPEZA"
    ACESSO = "ACESSO"
    OUTRO = "OUTRO"


class _Base(BaseModel):
    # camelCase no JSON, mas aceita também snake_case no código
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class IncidentCreate(_Base):
    category: Category
    location: str = Field(min_length=1, max_length=200, examples=["Bloco B, sala 2.14"])
    description: str = Field(min_length=1, examples=["Projetor não liga"])
    priority: Priority = Priority.MEDIA


class AssignRequest(_Base):
    technician_id: int = Field(examples=[2])
    version: int = Field(description="Versão do incidente que o cliente leu (controlo de concorrência)", examples=[1])


class StatusRequest(_Base):
    status: Status = Field(examples=["EM_CURSO"])
    version: int = Field(description="Versão do incidente que o cliente leu (controlo de concorrência)", examples=[2])


class CloseRequest(_Base):
    version: int = Field(description="Versão do incidente que o cliente leu (controlo de concorrência)", examples=[4])


class IncidentOut(_Base):
    id: int
    category: Category
    location: str
    description: str
    priority: Priority
    status: Status
    created_by: int
    assigned_to: int | None
    version: int
    created_at: datetime
    updated_at: datetime


class ErrorOut(BaseModel):
    """Formato de erro comum aos serviços."""
    detail: str