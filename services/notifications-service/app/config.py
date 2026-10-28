import os

# Ligação à base de dados do serviço (por omissão, a que corre no Docker, vista do PC)
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://notifications:notifications@localhost:2303/notificationsdb"
)

# Ligação ao RabbitMQ (por omissão, a porta vista do PC)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "2201"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

# Nomes combinados com o Serviço de Incidentes
EXCHANGE = "incidents.events"
FILA = "notifications.queue"
EXCHANGE_DLX = "incidents.dlx"
FILA_DLQ = "notifications.dlq"

# Tipos de evento que o serviço aceita
TIPOS_VALIDOS = {
    "INCIDENT_CREATED",
    "INCIDENT_ASSIGNED",
    "INCIDENT_UPDATED",
    "INCIDENT_CLOSED",
}