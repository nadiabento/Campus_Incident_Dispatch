"""Tabelas do serviço de incidentes."""
from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(30), nullable=False)
    location = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    created_by = Column(Integer, nullable=False)      # id do utilizador (users-service)
    assigned_to = Column(Integer, nullable=True)      # id do técnico atribuído
    # Número de versão para controlo otimista de concorrência:
    # sobe 1 em cada alteração; um pedido com versão antiga é rejeitado (409).
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OutboxEvent(Base):
    """
    Eventos à espera de serem publicados no RabbitMQ (padrão "transactional outbox").

    O evento é gravado na MESMA transação que a alteração ao incidente. Assim nunca
    se perde um evento nem se publica um evento de uma alteração que falhou, mesmo
    que o broker esteja em baixo. Um publicador em segundo plano envia-os depois.
    """
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True)             # ordem de publicação
    event_id = Column(String(36), unique=True, nullable=False)
    routing_key = Column(String(50), nullable=False)
    payload = Column(Text, nullable=False)             # JSON do evento
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)  # NULL = por enviar
    attempts = Column(Integer, nullable=False, default=0)