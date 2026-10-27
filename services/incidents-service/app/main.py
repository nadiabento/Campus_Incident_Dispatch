"""Arranque do Serviço de Incidentes."""
from fastapi import FastAPI
from app import config

app = FastAPI(
    title="Serviço de Incidentes",
    description="Gestão de incidentes do campus (Pessoa A)",
    version="1.0.0"
)

@app.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "service": "incidents-service",
        "exchange": config.EVENTS_EXCHANGE
    }

@app.get("/", tags=["root"])
def root():
    return {"message": "Serviço de Incidentes a correr com sucesso!"}