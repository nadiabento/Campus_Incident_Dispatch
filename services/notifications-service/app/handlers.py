from sqlalchemy.exc import IntegrityError
from app.models import Notification, ProcessedEvent

# Texto da notificação para cada tipo de evento
MENSAGENS = {
    "INCIDENT_CREATED": "Incidente {id} criado",
    "INCIDENT_ASSIGNED": "Incidente {id} atribuído a um técnico",
    "INCIDENT_UPDATED": "Estado do incidente {id} atualizado",
    "INCIDENT_CLOSED": "Incidente {id} encerrado",
}


def processar_evento(db, evento):
    # Devolve True se guardou uma notificação nova, False se o evento era duplicado
    event_id = str(evento["eventId"])

    # Se o evento já foi processado, ignora-o
    if db.get(ProcessedEvent, event_id):
        return False

    mensagem = MENSAGENS[evento["eventType"]].format(id=evento["incidentId"])
    try:
        # Regista o evento e a notificação na mesma transação
        db.add(ProcessedEvent(event_id=event_id))
        db.add(
            Notification(
                event_id=event_id,
                event_type=evento["eventType"],
                incident_id=str(evento["incidentId"]),
                version=evento.get("version"),
                message=mensagem,
            )
        )
        db.commit()
    except IntegrityError:
        # Outra instância guardou o mesmo evento ao mesmo tempo
        db.rollback()
        return False
    return True