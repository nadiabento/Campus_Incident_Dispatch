"""Testes com SQLite em memória e o users-service simulado (sem Docker)."""
import os

os.environ["DATABASE_URL"] = "sqlite://"   # tem de ser definido ANTES de importar a app

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import events, users_client
from app.database import Base, get_db
from app.main import app

# Utilizadores simulados (iguais em papéis aos do users-service)
USERS = {
    1: {"id": 1, "name": "Ana", "email": "ana@ua.pt", "role": "CAMPUS_USER"},
    2: {"id": 2, "name": "Rui", "email": "rui@ua.pt", "role": "TECHNICIAN"},
    3: {"id": 3, "name": "Eva", "email": "eva@ua.pt", "role": "ADMIN"},
    4: {"id": 4, "name": "Tó", "email": "to@ua.pt", "role": "TECHNICIAN"},
}


@pytest.fixture()
def client(monkeypatch):
    # BD nova em memória para cada teste
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def fake_get_user(user_id):
        if user_id not in USERS:
            raise users_client.UserNotFound(user_id)
        return USERS[user_id]

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(users_client, "get_user", fake_get_user)
    monkeypatch.setattr(events, "SessionLocal", Session)

    c = TestClient(app)   # sem "with": não corre o lifespan (nem o publicador do RabbitMQ)
    c.Session = Session   # para os testes lerem a tabela outbox
    yield c
    app.dependency_overrides.clear()


def hdr(user_id):
    """Cabeçalho que identifica quem faz o pedido."""
    return {"X-User-Id": str(user_id)}