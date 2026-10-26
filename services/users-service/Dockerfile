#parte de uma imagem que já tem Python
FROM python:3.12-slim  
# define a pasta de trabalho dentro do contentor
WORKDIR /app #
# copia a lista de bibliotecas
COPY requirements.txt .
# instala-as (acontece ao construir a imagem)
RUN pip install --no-cache-dir -r requirements.txt
# copia o código para dentro
COPY app ./app
# documenta que o serviço usa a porta 8000
EXPOSE 8000
# comando que arranca quando o contentor inicia
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]