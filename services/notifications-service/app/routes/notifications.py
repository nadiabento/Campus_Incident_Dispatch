from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[schemas.NotificationOut])
def list_notifications(
    incident_id: str | None = Query(None, alias="incidentId"),
    db: Session = Depends(get_db),
):
    """Lista o histórico de notificações. Com ?incidentId=... filtra por incidente."""
    consulta = db.query(models.Notification)
    if incident_id:
        consulta = consulta.filter(models.Notification.incident_id == incident_id)
    return consulta.order_by(models.Notification.id).all()