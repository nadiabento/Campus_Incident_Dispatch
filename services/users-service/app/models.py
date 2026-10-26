from sqlalchemy import Column, Integer, String
from app.database import Base


class User(Base):
    __tablename__ = "users"                              # nome da tabela
    id = Column(Integer, primary_key=True, index=True)   # número único, automático
    name = Column(String, nullable=False)                # obrigatório
    email = Column(String, unique=True, nullable=False)  # obrigatório e sem repetidos
    role = Column(String, nullable=False)                # papel do utilizador CAMPUS_USER | TECHNICIAN | ADMIN