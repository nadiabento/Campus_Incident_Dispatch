from fastapi import FastAPI
from app.database import Base, engine
from app.routes import users

Base.metadata.create_all(bind=engine)   # cria as tabelas se não existirem

app = FastAPI(title="Serviço de Utilizadores")

app.include_router(users.router)        # liga as rotas dos utilizadores

@app.get("/health")                     # endpoint simples para ver se está vivo
def health():
    return {"status": "ok"}