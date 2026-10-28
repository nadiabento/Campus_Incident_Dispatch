"""Arranque do Serviço de Incidentes."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app import config, events
from app.database import Base, SessionLocal, engine
from app.routes import incidents

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("incidents")

publisher = events.OutboxPublisher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria as tabelas (com algumas tentativas, caso a BD ainda esteja a arrancar)
    for attempt in range(1, 11):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except Exception as exc:
            log.warning("BD indisponível (%d/10): %s", attempt, exc)
            time.sleep(2)
    else:
        raise RuntimeError("Não foi possível ligar à base de dados")

    publisher.start()   # começa a publicar eventos em segundo plano
    yield
    publisher.stop()


app = FastAPI(
    title="Serviço de Incidentes",
    description="Gestão de incidentes do campus. Cada alteração gera um evento no RabbitMQ.\n\n"
                "O utilizador que faz o pedido é indicado no cabeçalho `X-User-Id`.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(incidents.router)


@app.get("/health", tags=["health"])
def health():
    """Estado do serviço: BD, ligação ao broker e eventos por publicar."""
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": "incidents-service",
        "exchange": config.EVENTS_EXCHANGE,
        "broker": "connected" if publisher.connected else "disconnected",
        "pendingEvents": events.pending_count(),
    }