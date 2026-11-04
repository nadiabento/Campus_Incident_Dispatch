# Cenários de teste

Pedidos prontos a executar em `requests.http` (secção indicada em cada cenário).
Pré-requisito: `docker compose up --build` com a base de dados vazia.
Convenção: ids 1 = Ana (CAMPUS_USER), 2 = Rui (TECHNICIAN), 3 = Eva (ADMIN), 4 = Tó (TECHNICIAN).

## Parte A - Serviço de Incidentes

### A1. Fluxo completo
**Pedidos:** secção 0 e secção 1 do `requests.http`.
**Esperado:**
- Estados e versões: ABERTO (v1) -> ATRIBUIDO (v2) -> EM_CURSO (v3) -> RESOLVIDO (v4) -> ENCERRADO (v5).
- Cada passo devolve 200 (o primeiro 201).
- Na consola do RabbitMQ (http://localhost:2202) e em `GET :2103/notifications?incidentId=1` aparecem 5 eventos: `INCIDENT_CREATED`, `INCIDENT_ASSIGNED`, `INCIDENT_UPDATED`, `INCIDENT_UPDATED`, `INCIDENT_CLOSED`.

### A2. Transições inválidas (máquina de estados)
**Pedidos:** 3.7, 3.8 e 3.9.
**Esperado:** 409 em ABERTO -> EM_CURSO e em fechar sem estar RESOLVIDO; 422 ao tentar atribuir por `/status`. Nenhum destes pedidos gera evento (`pendingEvents` não aumenta em `GET /health`).

### A3. Permissões por papel
**Pedidos:** 3.1, 3.2, 3.5, 3.6 e 3.10.
**Esperado:** 401 sem cabeçalho, 404 com utilizador inexistente, 403 para CAMPUS_USER a atribuir e para técnico não atribuído, 422 ao atribuir a quem não é TECHNICIAN.

### A4. Dados inválidos
**Pedido:** 3.3. **Esperado:** 422 com `{"detail": ...}`.

### A5. Conflito de versão (controlo otimista)
**Pedidos:** secção 4. **Esperado:** o 4.1 devolve 200 e o 4.2 devolve 409 com mensagem de conflito de versão. O 4.2 não gera evento.

### A6. Pedidos simultâneos sobre o mesmo incidente
Criar um incidente ABERTO (id N, version 1) e disparar dois pedidos ao mesmo tempo com a mesma versão:

```bash
N=3   # id de um incidente ABERTO com version 1
for tech in 2 4; do
  curl -s -o /dev/null -w "técnico $tech -> %{http_code}\n" -X PUT \
    http://localhost:2102/incidents/$N/assign \
    -H "Content-Type: application/json" -H "X-User-Id: 3" \
    -d "{\"technicianId\": $tech, \"version\": 1}" &
done; wait
```
**Esperado:** um 200 e um 409. `GET /incidents/N` mostra `version: 2` (só uma alteração entrou) e só existe um `INCIDENT_ASSIGNED` para esse incidente.

### A7. Consultas e filtros
**Pedidos:** secção 2. **Esperado:** filtros por `status`, `priority` e `assignedTo` devolvem só os incidentes correspondentes.

## Parte B - Tolerância a falhas (lado do Serviço de Incidentes)

### B1. Serviço de Utilizadores em baixo, com utilizador já conhecido (recurso)
1. Fazer um pedido com `X-User-Id: 3` (fica em cache).
2. `docker compose stop users-service`
3. Repetir um pedido com `X-User-Id: 3`.

**Esperado:** o pedido funciona com os dados em cache. Os logs do `incidents-service` mostram as tentativas falhadas e a mensagem de que está a usar a cache. No primeiro pedido há uma pequena demora (timeout e retries); a seguir o circuito fica aberto durante 15 s e as respostas são imediatas.

### B2. Serviço de Utilizadores em baixo, utilizador desconhecido
Com o `users-service` parado, usar um `X-User-Id` que ainda não foi consultado.
**Esperado:** 503 com `{"detail": "Serviço de utilizadores indisponível; ..."}`.

### B3. Recuperação
`docker compose start users-service` e repetir os pedidos. **Esperado:** voltam a funcionar normalmente, sem reiniciar o `incidents-service`.

### B4. RabbitMQ em baixo (outbox)
1. `docker compose stop rabbitmq`
2. Criar e atribuir incidentes (pedidos 1.1 e 1.2). **Esperado:** continuam a devolver 201/200.
3. `GET http://localhost:2102/health` -> `"broker": "disconnected"` e `pendingEvents` > 0. Os logs mostram "Falha na publicação de eventos" com espera crescente.
4. `docker compose start rabbitmq`. **Esperado:** em poucos segundos `pendingEvents` volta a 0, e as notificações dos incidentes criados durante a falha aparecem em `GET :2103/notifications`.

## Parte C - Cenários com o Serviço de Notificações (a completar com a Nadia)

### C1. Eventos duplicados
Publicar duas vezes o mesmo evento (mesmo `eventId`) com os scripts de `scripts/teste_rabbitmq/`. **Esperado:** só uma notificação registada.

### C2. Mensagem inválida e dead-letter queue
Publicar um evento sem `eventType` ou sem `incidentId`. **Esperado:** é rejeitado e vai para `notifications.dlq`.

### C3. Escalabilidade
Com `notifications-service` e `notifications-service-2` a correr, enviar N eventos. **Esperado:** os logs das duas instâncias mostram as mensagens repartidas entre elas.

## Registo de execução (preencher durante os testes)

| Cenário | Data | Resultado (OK/falhou) | Notas |
|---|---|---|---|
| A1 | 04/11/2026 | OK | Fluxo completo, versões 1 a 5, 5 eventos publicados |
| A2 | 04/11/2026 | OK | 3.7 e 3.8 deram 409, 3.9 deu 422, sem eventos |
| A3 | 04/11/2026 | OK | 401, 404, 403, 422 e 403 como esperado |
| A4 | 04/11/2026 | OK | 3.3 deu 422 |
| A5 | 04/11/2026 | OK | 4.1 deu 200 e 4.2 deu 409, sem evento no 4.2 |
| A6 | | | |
| A7 | | | |
| B1 | | | |
| B2 | | | |
| B3 | | | |
| B4 | | | |
| C1 | | | |
| C2 | | | |
| C3 | | | |