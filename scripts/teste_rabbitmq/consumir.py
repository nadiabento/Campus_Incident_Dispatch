import json

from rabbit import FILA, ligar

ligacao, canal = ligar()


# Esta função corre sempre que chega uma mensagem
def processar(canal, metodo, propriedades, corpo):
    try:
        # Converte o JSON e confirma que tem os campos essenciais
        evento = json.loads(corpo)
        tipo = evento["eventType"]
        incidente = evento["incidentId"]
    except (ValueError, KeyError, TypeError):
        # Mensagem inválida: rejeita sem voltar a pôr na fila, e vai para a dead-letter queue
        print("Mensagem inválida, enviada para a dead-letter queue")
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=False)
        return

    print("Recebido:", tipo, "incidente", incidente, "| eventId:", evento["eventId"])

    # Confirma o processamento, e só então a mensagem sai da fila
    canal.basic_ack(delivery_tag=metodo.delivery_tag)


# Recebe uma mensagem de cada vez, e só recebe a seguinte depois da confirmação
canal.basic_qos(prefetch_count=1)

# Começa a ouvir a fila, com confirmação manual (auto_ack=False)
canal.basic_consume(queue=FILA, on_message_callback=processar, auto_ack=False)

print("À espera de mensagens. Para parar, Ctrl+C.")
canal.start_consuming()