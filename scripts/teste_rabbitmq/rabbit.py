import pika

# Nomes combinados com o Serviço de Incidentes
EXCHANGE = "incidents.events"
FILA = "notifications.queue"
EXCHANGE_DLX = "incidents.dlx"
FILA_DLQ = "notifications.dlq"


def ligar():
    # Liga ao RabbitMQ pela porta do PC (2201)
    ligacao = pika.BlockingConnection(
        pika.ConnectionParameters(
            host="localhost",
            port=2201,
            credentials=pika.PlainCredentials("guest", "guest"),
        )
    )
    canal = ligacao.channel()

    # Cria a fila das mensagens que falham, com o seu exchange
    canal.exchange_declare(exchange=EXCHANGE_DLX, exchange_type="fanout", durable=True)
    canal.queue_declare(queue=FILA_DLQ, durable=True)
    canal.queue_bind(queue=FILA_DLQ, exchange=EXCHANGE_DLX)

    # Cria o exchange principal, onde o Serviço de Incidentes publica
    canal.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)

    # Cria a fila das notificações; as mensagens rejeitadas vão para a dead-letter queue
    canal.queue_declare(
        queue=FILA,
        durable=True,
        arguments={"x-dead-letter-exchange": EXCHANGE_DLX},
    )

    # Liga a fila a todos os eventos de incidentes (incident.*)
    canal.queue_bind(queue=FILA, exchange=EXCHANGE, routing_key="incident.*")

    return ligacao, canal