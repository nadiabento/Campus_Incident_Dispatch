"""
Eventos de incidentes e publicação no RabbitMQ.

Fluxo (padrão "transactional outbox"):
  1. A rota altera o incidente e chama enqueue_event() -> grava o evento na tabela
     outbox_events, na MESMA transação.
  2. O OutboxPublisher (thread em segundo plano) lê os eventos por enviar e publica-os
     no exchange, com confirmação do broker (publisher confirms).
  3. Se o broker estiver em baixo: regista o erro em log, espera (backoff) e tenta de novo.
     O evento fica na BD, por isso nada se perde. Só é marcado como enviado depois de o
     broker confirmar.

Garantia: "pelo menos uma vez". Pode haver duplicados, por isso o consumidor
deteta-os pelo eventId.
"""
import json
import logging
import threading
import uuid
from datetime import datetime, timezone

import pika
from sqlalchemy import func, select

from app import config
from app.database import SessionLocal
from app.models import Incident, OutboxEvent

log = logging.getLogger("incidents.events")

CREATED, ASSIGNED, UPDATED, CLOSED = (
    "INCIDENT_CREATED", "INCIDENT_ASSIGNED", "INCIDENT_UPDATED", "INCIDENT_CLOSED",
)
# INCIDENT_CREATED -> incident.created, etc.
ROUTING_KEYS = {t: "incident." + t.removeprefix("INCIDENT_").lower()
                for t in (CREATED, ASSIGNED, UPDATED, CLOSED)}


def build_event(event_type: str, incident: Incident, actor_id: int, actor_role: str) -> dict:
    """Monta o evento no formato combinado com o Serviço de Notificações."""
    return {
        "eventId": str(uuid.uuid4()),                      # único por mensagem (deteção de duplicados)
        "eventType": event_type,
        "incidentId": str(incident.id),
        "version": incident.version,                       # permite ordenar/descartar eventos antigos
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": {"userId": str(actor_id), "role": actor_role},
        "data": {
            "status": incident.status,
            "assignedTo": str(incident.assigned_to) if incident.assigned_to is not None else None,
            "category": incident.category,
            "priority": incident.priority,
        },
    }


def enqueue_event(db, event: dict) -> None:
    """Grava o evento na outbox (sem fazer commit: fica na transação do chamador)."""
    db.add(OutboxEvent(
        event_id=event["eventId"],
        routing_key=ROUTING_KEYS[event["eventType"]],
        payload=json.dumps(event),
    ))


def pending_count() -> int:
    """Nº de eventos ainda por publicar (usado no /health)."""
    with SessionLocal() as db:
        return db.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None))
        )


class OutboxPublisher(threading.Thread):
    """Publica em segundo plano os eventos da outbox."""

    def __init__(self):
        super().__init__(name="outbox-publisher", daemon=True)
        self._stop_flag = threading.Event()
        self._conn: pika.BlockingConnection | None = None
        self._channel = None
        self.connected = False

    # ---------- ligação ao broker ----------
    def _connect(self) -> None:
        params = pika.URLParameters(config.RABBITMQ_URL)
        params.socket_timeout = 5
        params.heartbeat = 30
        self._conn = pika.BlockingConnection(params)
        self._channel = self._conn.channel()
        # Declara o exchange (idempotente) para o serviço arrancar mesmo antes do consumidor
        self._channel.exchange_declare(
            exchange=config.EVENTS_EXCHANGE, exchange_type="topic", durable=True
        )
        self._channel.confirm_delivery()  # o broker confirma cada mensagem
        self.connected = True
        log.info("Ligado ao RabbitMQ")

    def _disconnect(self) -> None:
        self.connected = False
        try:
            if self._conn and self._conn.is_open:
                self._conn.close()
        except Exception:
            pass
        self._conn = self._channel = None

    # ---------- um ciclo: envia tudo o que estiver pendente ----------
    def _publish_pending(self) -> None:
        with SessionLocal() as db:
            # skip_locked: se houver 2 instâncias do serviço, não pegam nos mesmos eventos
            rows = db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.id)
                .limit(50)
                .with_for_update(skip_locked=True)
            ).all()
            for row in rows:
                row.attempts += 1
                try:
                    self._channel.basic_publish(
                        exchange=config.EVENTS_EXCHANGE,
                        routing_key=row.routing_key,
                        body=row.payload,
                        properties=pika.BasicProperties(
                            delivery_mode=2, content_type="application/json",
                            message_id=row.event_id,
                        ),
                    )
                except Exception:
                    db.commit()  # guarda o nº de tentativas
                    raise
                row.published_at = func.now()
                db.commit()  # só marca como enviado depois da confirmação do broker
                log.info("Evento publicado: %s (%s)", row.routing_key, row.event_id)

    # ---------- ciclo principal ----------
    def run(self) -> None:
        backoff = 1.0
        while not self._stop_flag.is_set():
            try:
                if self._conn is None:
                    self._connect()
                self._publish_pending()
                backoff = 1.0
                # "Dorme" 1s mas mantém os heartbeats da ligação vivos
                self._conn.process_data_events(time_limit=1)
            except Exception as exc:
                log.error("Falha na publicação de eventos (%s). Nova tentativa em %.0fs", exc, backoff)
                self._disconnect()
                self._stop_flag.wait(backoff)
                backoff = min(backoff * 2, config.PUBLISH_MAX_BACKOFF)
        self._disconnect()

    def stop(self) -> None:
        self._stop_flag.set()