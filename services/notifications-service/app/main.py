import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.consumer import correr
from app.database import Base, engine
from app.routes import notifications


@asynccontextmanager
async def lifespan(app):
    # Cria as tabelas se não existirem
    Base.metadata.create_all(bind=engine)
    # Arranca o consumidor numa thread própria
    threading.Thread(target=correr, daemon=True).start()
    yield


app = FastAPI(title="Serviço de Notificações", lifespan=lifespan)
app.include_router(notifications.router)


@app.get("/health")
def health():
    return {"status": "ok"}