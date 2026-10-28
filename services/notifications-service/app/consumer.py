import json
import time

import pika

from app import config
from app.database import SessionLocal
from app.handlers import processar_evento


def ligar():
    # Tenta ligar ao RabbitMQ até conseguir
    while True:
        try:
            return pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=config.RABBITMQ_HOST,
                    port=config.RABBITMQ_PORT,
                    credentials=pika.PlainCredentials(
                        config.RABBITMQ_USER, config.RABBITMQ_PASSWORD
                    ),
                    heartbeat=60,
                )
            )
        except pika.exceptions.AMQPError:
            print("RabbitMQ indisponível, nova tentativa em 5 segundos")
            time.sleep(5)


def declarar(canal):
    # Dead-letter queue e o seu exchange
    canal.exchange_declare(exchange=config.EXCHANGE_DLX, exchange_type="fanout", durable=True)
    canal.queue_declare(queue=config.FILA_DLQ, durable=True)
    canal.queue_bind(queue=config.FILA_DLQ, exchange=config.EXCHANGE_DLX)
    # Exchange principal e fila das notificações
    canal.exchange_declare(exchange=config.EXCHANGE, exchange_type="topic", durable=True)
    canal.queue_declare(
        queue=config.FILA,
        durable=True,
        arguments={"x-dead-letter-exchange": config.EXCHANGE_DLX},
    )
    canal.queue_bind(queue=config.FILA, exchange=config.EXCHANGE, routing_key="incident.*")


def evento_valido(evento):
    # Confirma que a mensagem tem os campos essenciais e um tipo conhecido
    return (
        isinstance(evento, dict)
        and evento.get("eventType") in config.TIPOS_VALIDOS
        and bool(evento.get("incidentId"))
        and bool(evento.get("eventId"))
    )


def processar(canal, metodo, propriedades, corpo):
    # Corre sempre que chega uma mensagem
    try:
        evento = json.loads(corpo)
    except ValueError:
        evento = None

    # Mensagem inválida: rejeita sem recolocar, vai para a dead-letter queue
    if not evento_valido(evento):
        print("Mensagem inválida, enviada para a dead-letter queue")
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=False)
        return

    db = SessionLocal()
    try:
        novo = processar_evento(db, evento)
        if novo:
            print("Notificação guardada:", evento["eventType"], evento["incidentId"])
        else:
            print("Evento duplicado ignorado:", evento["eventId"])
        # Confirma o processamento, e a mensagem sai da fila
        canal.basic_ack(delivery_tag=metodo.delivery_tag)
    except Exception as erro:
        db.rollback()
        print("Erro ao processar:", erro)
        # Na primeira falha volta à fila; se falhar outra vez, vai para a dead-letter queue
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=not metodo.redelivered)
    finally:
        db.close()


def correr():
    # Ciclo principal: se a ligação cair, volta a ligar
    while True:
        try:
            ligacao = ligar()
            canal = ligacao.channel()
            declarar(canal)
            # Uma mensagem de cada vez
            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(queue=config.FILA, on_message_callback=processar, auto_ack=False)
            print("Consumidor ativo, à espera de mensagens")
            canal.start_consuming()
        except pika.exceptions.AMQPError as erro:
            print("Ligação ao RabbitMQ perdida:", erro)
            time.sleep(5)