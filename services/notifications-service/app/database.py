from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

# Ligação à base de dados
engine = create_engine(DATABASE_URL)
# Fábrica de sessões
SessionLocal = sessionmaker(bind=engine)
# Classe-mãe dos modelos
Base = declarative_base()


def get_db():
    # Abre uma sessão por pedido e fecha-a no fim
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()