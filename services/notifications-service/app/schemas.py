from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    # Formato com que a notificação é devolvida pela API
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: str
    event_type: str
    incident_id: str
    version: int | None
    message: str
    created_at: datetime