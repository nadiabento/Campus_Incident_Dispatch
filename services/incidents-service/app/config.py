"""Configuração do serviço, lida das variáveis de ambiente."""
import os

# Base de dados própria do serviço de incidentes
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://incidents:incidents@localhost:2302/incidentsdb"
)

# Serviço de utilizadores (dentro do Docker: http://users-service:8000)
USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://localhost:2101")
USERS_TIMEOUT = float(os.getenv("USERS_TIMEOUT", "2"))            # segundos por tentativa
USERS_RETRIES = int(os.getenv("USERS_RETRIES", "3"))              # nº de tentativas
USERS_BACKOFF = float(os.getenv("USERS_BACKOFF", "0.3"))          # espera base entre tentativas
USERS_CACHE_TTL = int(os.getenv("USERS_CACHE_TTL", "600"))        # validade da cache de recurso (s)

# Broker de mensagens
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:2201/%2F")
EVENTS_EXCHANGE = os.getenv("EVENTS_EXCHANGE", "incidents.events")
PUBLISH_MAX_BACKOFF = float(os.getenv("PUBLISH_MAX_BACKOFF", "30"))  # espera máxima entre retries (s)
