from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL) # a "ligação" à base de dados
SessionLocal = sessionmaker(bind=engine)  # fábrica de sessões (conversas com a BD)
Base = declarative_base()  # classe-mãe dos modelos (tabelas)
 

def get_db():
    db = SessionLocal()   # abre uma sessão
    try:
        yield db # entrega-a ao pedido que precisa
    finally:
        db.close()   # fecha sempre no fim, mesmo se der erro