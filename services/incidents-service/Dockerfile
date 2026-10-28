# Imagem base com Python
FROM python:3.12-slim
# Pasta de trabalho dentro do contentor
WORKDIR /app
# Instala as dependências primeiro (aproveita a cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copia o código (o .venv fica de fora, porque só copiamos a pasta app)
COPY app ./app
# Documenta que o serviço usa a porta 8000
EXPOSE 8000
# Arranca a API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]