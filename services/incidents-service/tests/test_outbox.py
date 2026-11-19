"""Testes do publicador da outbox (OutboxPublisher), sem RabbitMQ real.

Usam um canal falso: ora falha (broker em baixo), ora regista o que foi publicado.
"""
import json

import pytest

from app import events
from app.models import OutboxEvent
from tests.conftest import hdr

NEW = {"category": "REDE", "location": "Biblioteca", "description": "Sem wifi", "priority": "MEDIA"}


class BrokerDown:
    """Canal falso: qualquer publicação falha, como se o broker estivesse em baixo."""
    def basic_publish(self, **kwargs):
        raise ConnectionError("broker em baixo")


class FakeChannel:
    """Canal falso: guarda o que foi publicado (como se o broker confirmasse tudo)."""
    def __init__(self):
        self.published = []

    def basic_publish(self, exchange, routing_key, body, properties):
        self.published.append((exchange, routing_key, json.loads(body), properties))


def _publisher(channel):
    pub = events.OutboxPublisher()
    pub._channel = channel   # injeta o canal falso (não chama _connect)
    return pub


def _rows(client):
    with client.Session() as db:
        return db.query(OutboxEvent).order_by(OutboxEvent.id).all()


def test_event_stays_in_outbox_when_broker_is_down(client):
    assert client.post("/incidents", json=NEW, headers=hdr(1)).status_code == 201

    with pytest.raises(ConnectionError):
        _publisher(BrokerDown())._publish_pending()

    row = _rows(client)[0]
    assert row.published_at is None          # não foi marcado como enviado
    assert row.attempts == 1                 # mas a tentativa ficou registada
    assert events.pending_count() == 1       # e aparece como pendente (/health)


def test_pending_events_are_published_when_broker_returns(client):
    r = client.post("/incidents", json=NEW, headers=hdr(1))
    inc = r.json()
    client.put(f"/incidents/{inc['id']}/assign",
               json={"technicianId": 2, "version": inc["version"]}, headers=hdr(3))

    # 1.ª tentativa: broker em baixo -> nada é publicado
    with pytest.raises(ConnectionError):
        _publisher(BrokerDown())._publish_pending()
    assert events.pending_count() == 2

    # 2.ª tentativa: o broker voltou -> publica os dois, pela ordem em que foram criados
    channel = FakeChannel()
    _publisher(channel)._publish_pending()

    assert events.pending_count() == 0
    assert [p[1] for p in channel.published] == ["incident.created", "incident.assigned"]
    assert [p[2]["version"] for p in channel.published] == [1, 2]
    exchange, _, event, props = channel.published[0]
    assert exchange == "incidents.events"
    assert props.delivery_mode == 2                       # mensagem persistente
    assert props.message_id == event["eventId"]           # message_id = eventId
    rows = _rows(client)
    assert all(row.published_at is not None for row in rows)
    # o 1.º evento foi tentado duas vezes (falhou e depois passou); o 2.º só uma vez,
    # porque a falha interrompeu o ciclo logo no 1.º
    assert [row.attempts for row in rows] == [2, 1]


def test_published_events_are_not_sent_twice(client):
    client.post("/incidents", json=NEW, headers=hdr(1))
    channel = FakeChannel()
    pub = _publisher(channel)
    pub._publish_pending()
    pub._publish_pending()                                # 2.º ciclo: já não há nada por enviar
    assert len(channel.published) == 1
