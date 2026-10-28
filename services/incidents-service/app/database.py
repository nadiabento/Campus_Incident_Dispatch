"""Ligação à base de dados do serviço de incidentes."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

# O SQLite (usado só nos testes) precisa desta opção; o Postgres não.
_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping: testa a ligação antes de a usar (recupera de quedas da BD)
engine = create_engine(DATABASE_URL, connect_args=_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


def get_db():
    """Abre uma sessão por pedido e fecha-a sempre no fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()