from sqlalchemy import Column, DateTime, Integer, String, func
from app.database import Base


class Notification(Base):
    # Histórico de notificações
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, nullable=False)           # id do evento que a originou
    event_type = Column(String, nullable=False)         # tipo do evento
    incident_id = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=True)            # versão do incidente
    message = Column(String, nullable=False)            # texto da notificação
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProcessedEvent(Base):
    # Eventos já processados, usada para detetar duplicados
    __tablename__ = "processed_events"

    event_id = Column(String, primary_key=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())