"""
Rotas REST dos incidentes.

Quem faz o pedido? Vem no cabeçalho X-User-Id (não há autenticação completa, como
permite o enunciado). O papel é obtido no Serviço de Utilizadores.

Permissões por papel:
  criar          -> qualquer utilizador registado
  listar/detalhe -> aberto (sem cabeçalho)
  atribuir       -> ADMIN
  mudar estado   -> ADMIN, ou o TECHNICIAN a quem o incidente está atribuído
  encerrar       -> ADMIN, ou o TECHNICIAN a quem o incidente está atribuído
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app import events, schemas, users_client
from app.database import get_db
from app.models import Incident
from app.state_machine import Status, can_transition

router = APIRouter(prefix="/incidents", tags=["incidents"])

# Respostas de erro documentadas no OpenAPI/Swagger
ERR = {
    401: {"model": schemas.ErrorOut, "description": "Cabeçalho X-User-Id em falta"},
    403: {"model": schemas.ErrorOut, "description": "O papel do utilizador não permite a operação"},
    404: {"model": schemas.ErrorOut, "description": "Incidente ou utilizador não encontrado"},
    409: {"model": schemas.ErrorOut, "description": "Transição inválida ou conflito de versão"},
    503: {"model": schemas.ErrorOut, "description": "Serviço de utilizadores indisponível"},
}


# ---------------------------------------------------------------- auxiliares
def _fetch_user(user_id: int) -> dict:
    """Obtém um utilizador (com timeout/retries/recurso) e traduz erros para HTTP."""
    try:
        return users_client.get_user(user_id)
    except users_client.UserNotFound:
        raise HTTPException(404, f"Utilizador {user_id} não encontrado")
    except users_client.UsersUnavailable:
        raise HTTPException(503, "Serviço de utilizadores indisponível; tente novamente mais tarde")


def current_actor(x_user_id: int | None = Header(default=None, description="Id do utilizador que faz o pedido")) -> dict:
    """Dependência: identifica e valida quem faz o pedido."""
    if x_user_id is None:
        raise HTTPException(401, "Cabeçalho X-User-Id em falta")
    user = _fetch_user(x_user_id)
    return {"id": user["id"], "role": user["role"]}


def _get_or_404(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incidente não encontrado")
    return incident


def _require_admin_or_assigned_tech(actor: dict, incident: Incident) -> None:
    if actor["role"] == "ADMIN":
        return
    if actor["role"] == "TECHNICIAN" and incident.assigned_to == actor["id"]:
        return
    raise HTTPException(403, "Só o ADMIN ou o técnico atribuído podem executar esta operação")


def _check_transition(incident: Incident, target: Status) -> None:
    if not can_transition(Status(incident.status), target):
        raise HTTPException(409, f"Transição inválida: {incident.status} -> {target.value}")


def _apply_change(db: Session, incident: Incident, expected_version: int, changes: dict,
                  event_type: str, actor: dict) -> Incident:
    """
    Aplica uma alteração com CONTROLO OTIMISTA DE CONCORRÊNCIA.

    O UPDATE só acontece se a versão na BD ainda for a que o cliente leu
    (WHERE version = :esperada) e incrementa-a no mesmo comando. Se dois pedidos
    chegarem ao mesmo tempo, a BD só deixa passar um; o outro afeta 0 linhas -> 409.
    O evento é gravado na outbox na mesma transação.
    """
    if incident.version != expected_version:  # falha rápida (caso comum, sem corrida)
        raise HTTPException(
            409, f"Conflito de versão: enviou {expected_version}, versão atual é {incident.version}")

    result = db.execute(
        update(Incident)
        .where(Incident.id == incident.id, Incident.version == expected_version)
        .values(**changes, version=Incident.version + 1, updated_at=func.now())
    )
    if result.rowcount == 0:  # alguém alterou entre a leitura e o UPDATE
        db.rollback()
        raise HTTPException(409, "Conflito de versão: o incidente foi alterado por outro pedido")

    db.refresh(incident)  # recarrega com a nova versão
    events.enqueue_event(db, events.build_event(event_type, incident, actor["id"], actor["role"]))
    db.commit()  # alteração + evento ficam gravados juntos (ou nenhum)
    return incident


# --------------------------------------------------------------------- rotas
@router.post("", response_model=schemas.IncidentOut, status_code=201,
             responses={k: ERR[k] for k in (401, 404, 503)}, summary="Criar incidente")
def create_incident(data: schemas.IncidentCreate, actor: dict = Depends(current_actor),
                    db: Session = Depends(get_db)):
    incident = Incident(
        category=data.category.value, location=data.location, description=data.description,
        priority=data.priority.value, status=Status.ABERTO.value,
        created_by=actor["id"], version=1,
    )
    db.add(incident)
    db.flush()  # obtém o id antes de montar o evento
    db.refresh(incident)
    events.enqueue_event(db, events.build_event(events.CREATED, incident, actor["id"], actor["role"]))
    db.commit()
    return incident


@router.get("", response_model=list[schemas.IncidentOut], summary="Listar incidentes")
def list_incidents(
    status: Status | None = Query(default=None, description="Filtrar por estado"),
    priority: schemas.Priority | None = Query(default=None, description="Filtrar por prioridade"),
    assigned_to: int | None = Query(default=None, alias="assignedTo", description="Filtrar por técnico"),
    db: Session = Depends(get_db),
):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status.value)
    if priority:
        query = query.filter(Incident.priority == priority.value)
    if assigned_to is not None:
        query = query.filter(Incident.assigned_to == assigned_to)
    return query.order_by(Incident.id).all()


@router.get("/{incident_id}", response_model=schemas.IncidentOut,
            responses={404: ERR[404]}, summary="Detalhe de um incidente")
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, incident_id)


@router.put("/{incident_id}/assign", response_model=schemas.IncidentOut,
            responses=ERR, summary="Atribuir (ou reatribuir) a um técnico")
def assign_incident(incident_id: int, data: schemas.AssignRequest,
                    actor: dict = Depends(current_actor), db: Session = Depends(get_db)):
    if actor["role"] != "ADMIN":
        raise HTTPException(403, "Só o ADMIN pode atribuir incidentes")
    incident = _get_or_404(db, incident_id)
    technician = _fetch_user(data.technician_id)
    if technician["role"] != "TECHNICIAN":
        raise HTTPException(422, f"O utilizador {data.technician_id} não é TECHNICIAN")
    _check_transition(incident, Status.ATRIBUIDO)
    return _apply_change(db, incident, data.version,
                         {"status": Status.ATRIBUIDO.value, "assigned_to": technician["id"]},
                         events.ASSIGNED, actor)


@router.put("/{incident_id}/status", response_model=schemas.IncidentOut,
            responses=ERR, summary="Atualizar o estado")
def update_status(incident_id: int, data: schemas.StatusRequest,
                  actor: dict = Depends(current_actor), db: Session = Depends(get_db)):
    # ATRIBUIDO e ENCERRADO têm endpoints próprios (precisam de dados/regras específicas)
    if data.status == Status.ATRIBUIDO:
        raise HTTPException(422, "Para atribuir use PUT /incidents/{id}/assign")
    if data.status == Status.ENCERRADO:
        raise HTTPException(422, "Para encerrar use PUT /incidents/{id}/close")
    incident = _get_or_404(db, incident_id)
    _require_admin_or_assigned_tech(actor, incident)
    _check_transition(incident, data.status)
    return _apply_change(db, incident, data.version, {"status": data.status.value},
                         events.UPDATED, actor)


@router.put("/{incident_id}/close", response_model=schemas.IncidentOut,
            responses=ERR, summary="Encerrar (só a partir de RESOLVIDO)")
def close_incident(incident_id: int, data: schemas.CloseRequest,
                   actor: dict = Depends(current_actor), db: Session = Depends(get_db)):
    incident = _get_or_404(db, incident_id)
    _require_admin_or_assigned_tech(actor, incident)
    _check_transition(incident, Status.ENCERRADO)
    return _apply_change(db, incident, data.version, {"status": Status.ENCERRADO.value},
                         events.CLOSED, actor)
