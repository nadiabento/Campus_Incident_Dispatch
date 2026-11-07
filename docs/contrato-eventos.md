# Contrato de eventos

Acordo entre o Serviço de Incidentes (produtor) e o Serviço de Notificações (consumidor).
Estado: **proposta, a confirmar com a Nadia** (ver "Pontos em aberto" no fim).

## 1. Broker, exchange e filas

| Item | Valor |
|---|---|
| Broker | RabbitMQ |
| Exchange | `incidents.events` (tipo `topic`, durável) |
| Fila das notificações | `notifications.queue` (durável), ligada ao exchange com a routing key `incident.*` |
| Dead-letter exchange | `incidents.dlx` (fanout, durável) |
| Dead-letter queue | `notifications.dlq` (durável), ligada a `incidents.dlx` |

## 2. Tipos de evento e routing keys

| `eventType` | Routing key | Quando o Serviço de Incidentes o gera |
|---|---|---|
| `INCIDENT_CREATED` | `incident.created` | `POST /incidents` |
| `INCIDENT_ASSIGNED` | `incident.assigned` | `PUT /incidents/{id}/assign` (inclui reatribuir) |
| `INCIDENT_UPDATED` | `incident.updated` | `PUT /incidents/{id}/status` (EM_CURSO, RESOLVIDO, reabrir) |
| `INCIDENT_CLOSED` | `incident.closed` | `PUT /incidents/{id}/close` |

Um pedido rejeitado (401, 403, 404, 409, 422) **não gera evento**.

## 3. Formato da mensagem (JSON)

```json
{
  "eventId": "c98211c5-71d8-4684-862d-ee67b367e660",
  "eventType": "INCIDENT_ASSIGNED",
  "incidentId": "2",
  "version": 2,
  "timestamp": "2026-11-04T22:35:25.963+00:00",
  "actor": { "userId": "3", "role": "ADMIN" },
  "data": {
    "status": "ATRIBUIDO",
    "assignedTo": "2",
    "category": "EQUIPAMENTO",
    "priority": "ALTA"
  }
}
```

| Campo | Tipo | Significado |
|---|---|---|
| `eventId` | string (UUID) | Único por mensagem. O consumidor usa-o para detetar duplicados |
| `eventType` | string | Um dos 4 tipos acima. Obrigatório |
| `incidentId` | string | Id do incidente. Obrigatório |
| `version` | inteiro | Versão do incidente **depois** da alteração. Cresce 1 a 1 por incidente (1 = criação) |
| `timestamp` | string ISO 8601 (UTC) | Momento em que o evento foi criado |
| `actor.userId` / `actor.role` | string / string | Quem fez o pedido (`CAMPUS_USER`, `TECHNICIAN` ou `ADMIN`) |
| `data.status` | string | `ABERTO`, `ATRIBUIDO`, `EM_CURSO`, `RESOLVIDO` ou `ENCERRADO` |
| `data.assignedTo` | string ou `null` | Id do técnico atribuído. `null` enquanto não houver |
| `data.category` | string | `ELETRICO`, `REDE`, `EQUIPAMENTO`, `SALA`, `LIMPEZA`, `ACESSO` ou `OUTRO` |
| `data.priority` | string | `BAIXA`, `MEDIA`, `ALTA` ou `CRITICA` |

Propriedades AMQP de cada mensagem: `delivery_mode = 2` (persistente), `content_type = application/json`, `message_id = eventId`.

## 4. Garantias de entrega

- **Pelo menos uma vez.** O produtor grava o evento numa tabela (`outbox_events`) na mesma transação que altera o incidente, e uma thread publica-o com confirmação do broker. Se o broker estiver em baixo, o evento fica guardado e sai quando ele voltar. Pode, por isso, haver duplicados.
- **Duplicados:** o consumidor processa cada `eventId` uma só vez.
- **Ordem:** a ordem de **publicação** respeita a ordem das alterações. Com duas instâncias a consumir da mesma fila, a ordem de **processamento** não é garantida (o `CREATED` e o `ASSIGNED` do mesmo incidente podem ser tratados por instâncias diferentes). O campo `version` permite ao consumidor ordenar ou descartar eventos antigos.

## 5. Regras do consumidor (Serviço de Notificações)

- Rejeita (sem recolocar) mensagens sem `eventType` ou sem `incidentId`; vão para `notifications.dlq`.
- Acknowledgement manual; numa falha de processamento volta à fila uma vez e, se falhar outra vez, vai para a dead-letter queue.

## Pontos em aberto

1. **Quem declara a fila e o binding.** Hoje é o consumidor que declara o exchange, a fila, a DLQ e o binding `incident.*`; o `infra/rabbitmq/definitions.json` está vazio. O produtor só declara o exchange. Se o produtor publicar antes de a fila existir, o RabbitMQ descarta as mensagens sem erro. Propor: declarar tudo em `definitions.json`, ou o produtor declarar também a fila.
2. Confirmar que os campos extra em `data` (`category`, `priority`) não causam problemas ao consumidor.
3. Confirmar o uso de `version` para tratar eventos fora de ordem (ou aceitar que as notificações sejam informativas e a ordem não importe).