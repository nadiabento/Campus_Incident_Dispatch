import json

import httpx
import pytest

from app import config, users_client
from app.models import OutboxEvent
from app.state_machine import Status, can_transition
from tests.conftest import hdr

NEW = {"category": "EQUIPAMENTO", "location": "Bloco B 2.14",
       "description": "Projetor avariado", "priority": "ALTA"}


def create(client, user=1):
    r = client.post("/incidents", json=NEW, headers=hdr(user))
    assert r.status_code == 201, r.text
    return r.json()


def assign(client, inc, tech=2, user=3):
    return client.put(f"/incidents/{inc['id']}/assign",
                      json={"technicianId": tech, "version": inc["version"]}, headers=hdr(user))


# ---------------- máquina de estados ----------------
def test_state_machine_rules():
    assert can_transition(Status.ABERTO, Status.ATRIBUIDO)
    assert can_transition(Status.RESOLVIDO, Status.EM_CURSO)
    assert not can_transition(Status.ABERTO, Status.EM_CURSO)
    assert not can_transition(Status.ENCERRADO, Status.ABERTO)


# ---------------- fluxo completo + eventos ----------------
def test_full_flow_and_events(client):
    inc = create(client)
    assert inc["status"] == "ABERTO" and inc["version"] == 1 and inc["createdBy"] == 1

    inc = assign(client, inc).json()
    assert inc["status"] == "ATRIBUIDO" and inc["assignedTo"] == 2 and inc["version"] == 2

    for status in ("EM_CURSO", "RESOLVIDO"):
        r = client.put(f"/incidents/{inc['id']}/status",
                       json={"status": status, "version": inc["version"]}, headers=hdr(2))
        assert r.status_code == 200, r.text
        inc = r.json()

    r = client.put(f"/incidents/{inc['id']}/close", json={"version": inc["version"]}, headers=hdr(3))
    assert r.status_code == 200 and r.json()["status"] == "ENCERRADO" and r.json()["version"] == 5

    # 5 alterações -> 5 eventos na outbox, com os tipos certos e versões crescentes
    with client.Session() as db:
        rows = db.query(OutboxEvent).order_by(OutboxEvent.id).all()
    evs = [json.loads(r.payload) for r in rows]
    assert [e["eventType"] for e in evs] == [
        "INCIDENT_CREATED", "INCIDENT_ASSIGNED", "INCIDENT_UPDATED",
        "INCIDENT_UPDATED", "INCIDENT_CLOSED"]
    assert [e["version"] for e in evs] == [1, 2, 3, 4, 5]
    assert rows[0].routing_key == "incident.created"
    assert len({e["eventId"] for e in evs}) == 5                      # eventIds únicos
    assert evs[1]["data"]["assignedTo"] == "2"
    assert evs[1]["actor"] == {"userId": "3", "role": "ADMIN"}


def test_invalid_transition_409(client):
    inc = create(client)
    r = client.put(f"/incidents/{inc['id']}/status",
                   json={"status": "EM_CURSO", "version": 1}, headers=hdr(3))
    assert r.status_code == 409 and "Transição inválida" in r.json()["detail"]


def test_close_only_from_resolved(client):
    inc = create(client)
    r = client.put(f"/incidents/{inc['id']}/close", json={"version": 1}, headers=hdr(3))
    assert r.status_code == 409


# ---------------- coordenação: controlo de versões ----------------
def test_stale_version_409_and_no_event(client):
    inc = create(client)
    assert assign(client, inc, tech=2).status_code == 200            # versão passa a 2
    r = assign(client, inc, tech=4)                                  # reutiliza a versão 1 (antiga)
    assert r.status_code == 409 and "versão" in r.json()["detail"]
    with client.Session() as db:
        assert db.query(OutboxEvent).count() == 2                    # o pedido rejeitado não gerou evento


# ---------------- permissões ----------------
def test_permissions(client):
    inc = create(client)
    assert assign(client, inc, user=1).status_code == 403            # CAMPUS_USER não atribui
    assert assign(client, inc, user=2).status_code == 403            # TECHNICIAN não atribui
    inc = assign(client, inc).json()                                 # o ADMIN atribui ao técnico 2
    body = {"status": "EM_CURSO", "version": inc["version"]}
    r = client.put(f"/incidents/{inc['id']}/status", json=body, headers=hdr(4))
    assert r.status_code == 403                                      # outro técnico não mexe
    r = client.put(f"/incidents/{inc['id']}/status", json=body, headers=hdr(2))
    assert r.status_code == 200                                      # o técnico atribuído pode


def test_assign_requires_technician(client):
    inc = create(client)
    assert assign(client, inc, tech=1).status_code == 422            # 1 é CAMPUS_USER
    assert assign(client, inc, tech=99).status_code == 404           # não existe


def test_missing_or_unknown_user(client):
    assert client.post("/incidents", json=NEW).status_code == 401
    assert client.post("/incidents", json=NEW, headers=hdr(99)).status_code == 404


def test_status_endpoint_rejects_assign_and_close(client):
    inc = create(client)
    for s in ("ATRIBUIDO", "ENCERRADO"):
        r = client.put(f"/incidents/{inc['id']}/status",
                       json={"status": s, "version": 1}, headers=hdr(3))
        assert r.status_code == 422


# ---------------- consulta ----------------
def test_list_filters_and_detail(client):
    a = create(client)
    create(client)
    assign(client, a)
    assert len(client.get("/incidents").json()) == 2
    assert len(client.get("/incidents?status=ATRIBUIDO").json()) == 1
    assert len(client.get("/incidents?priority=BAIXA").json()) == 0
    assert client.get(f"/incidents/{a['id']}").json()["status"] == "ATRIBUIDO"
    assert client.get("/incidents/999").status_code == 404


def test_validation_422(client):
    r = client.post("/incidents", json={"category": "XPTO", "location": "", "description": "x"},
                    headers=hdr(1))
    assert r.status_code == 422


# ---------------- tolerância a falhas: users-service ----------------
def test_users_client_retries_then_unavailable_without_cache(monkeypatch):
    users_client.clear_cache()
    monkeypatch.setattr(config, "USERS_BACKOFF", 0)
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    with pytest.raises(users_client.UsersUnavailable):
        users_client.get_user(1)
    assert len(calls) == config.USERS_RETRIES                        # fez todas as tentativas


def test_users_client_falls_back_to_cache(monkeypatch):
    users_client.clear_cache()
    monkeypatch.setattr(config, "USERS_BACKOFF", 0)

    class Resp:
        status_code = 200
        def json(self):
            return {"id": 1, "name": "Ana", "email": "a@a", "role": "ADMIN"}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: Resp())
    assert users_client.get_user(1)["role"] == "ADMIN"               # preenche a cache

    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    assert users_client.get_user(1)["role"] == "ADMIN"   