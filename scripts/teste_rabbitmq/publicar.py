import json
import sys
import uuid
from datetime import datetime, timezone

import pika

from rabbit import EXCHANGE, ligar

# O tipo de evento vem da linha de comandos; por omissão é INCIDENT_CREATED
tipo = sys.argv[1] if len(sys.argv) > 1 else "INCIDENT_CREATED"
incidente = sys.argv[2] if len(sys.argv) > 2 else "1"

ligacao, canal = ligar()

if tipo == "INVALIDO":
    # Mensagem propositadamente inválida, para testar a dead-letter queue
    corpo = "isto não é json"
    routing_key = "incident.created"
else:
    # Monta um evento de exemplo com identificador único
    evento = {
        "eventId": str(uuid.uuid4()),
        "eventType": tipo,
        "incidentId": incidente,
        "version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": {"userId": "1", "role": "CAMPUS_USER"},
        "data": {"status": "ABERTO"},
    }
    corpo = json.dumps(evento)
    # INCIDENT_CREATED passa a incident.created, e assim por diante
    routing_key = "incident." + tipo.replace("INCIDENT_", "").lower()

# Envia a mensagem; delivery_mode=2 pede ao RabbitMQ para a guardar em disco
canal.basic_publish(
    exchange=EXCHANGE,
    routing_key=routing_key,
    body=corpo,
    properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
)

print("Enviado:", routing_key)
ligacao.close()