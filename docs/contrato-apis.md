# Contrato das APIs

Estado: **proposta, a confirmar com a Nadia**.

## 1. Convenções comuns

| Item | Valor |
|---|---|
| Formato | JSON. No Serviço de Incidentes os campos vão em camelCase (`assignedTo`, `createdBy`, `technicianId`) |
| Formato de erro | `{"detail": "mensagem"}` nos dois serviços |
| Quem faz o pedido | Cabeçalho `X-User-Id` (id de um utilizador registado). Sem autenticação completa |
| Papéis | `CAMPUS_USER`, `TECHNICIAN`, `ADMIN` |
| Documentação | Swagger em `/docs` de cada serviço |

| Serviço | Porta no PC | Porta no contentor |
|---|---|---|
| Utilizadores | 2101 | 8000 |
| Incidentes | 2102 | 8000 |
| Notificações | 2103 e 2104 (2.ª instância) | 8000 |

Dentro do Docker, o Serviço de Incidentes chama o de Utilizadores em `http://users-service:8000`.

## 2. Estados do incidente e transições válidas

`ABERTO → ATRIBUIDO → EM_CURSO → RESOLVIDO → ENCERRADO`

| Estado atual | Pode passar a |
|---|---|
| `ABERTO` | `ATRIBUIDO` |
| `ATRIBUIDO` | `ATRIBUIDO` (reatribuir), `EM_CURSO` |
| `EM_CURSO` | `RESOLVIDO` |
| `RESOLVIDO` | `EM_CURSO` (reabrir), `ENCERRADO` |
| `ENCERRADO` | nenhum (estado final) |

Transição inválida: **409**.

## 3. Serviço de Incidentes (porta 2102)

| Endpoint | Quem pode | Corpo do pedido | Resposta |
|---|---|---|---|
| `POST /incidents` | Qualquer utilizador registado | `category`, `location`, `description`, `priority` (opcional, por omissão `MEDIA`) | 201 com o incidente (`ABERTO`, `version` 1) |
| `GET /incidents` | Qualquer | Filtros opcionais: `status`, `priority`, `assignedTo` | 200 com a lista |
| `GET /incidents/{id}` | Qualquer | | 200 ou 404 |
| `PUT /incidents/{id}/assign` | `ADMIN` | `technicianId`, `version` | 200 com o incidente (`ATRIBUIDO`) |
| `PUT /incidents/{id}/status` | `ADMIN` ou o técnico atribuído | `status` (`EM_CURSO`, `RESOLVIDO`), `version` | 200 com o incidente |
| `PUT /incidents/{id}/close` | `ADMIN` ou o técnico atribuído | `version` | 200 (`ENCERRADO`) |
| `GET /health` | Qualquer | | 200 com `status`, `broker` e `pendingEvents` |

Campos do incidente na resposta: `id`, `category`, `location`, `description`, `priority`, `status`, `createdBy`, `assignedTo`, `version`, `createdAt`, `updatedAt`.

**Controlo de concorrência:** os pedidos de alteração levam a `version` que o cliente leu. Se o incidente já tiver outra versão (por exemplo, dois pedidos ao mesmo tempo), o segundo falha com **409**.

### Códigos de erro

| Código | Quando |
|---|---|
| 401 | Falta o cabeçalho `X-User-Id` |
| 403 | O papel não pode executar a operação, ou o técnico não é o atribuído |
| 404 | Incidente ou utilizador inexistente |
| 409 | Transição de estado inválida, ou conflito de versão |
| 422 | Dados inválidos; atribuir a quem não é `TECHNICIAN`; usar `/status` para `ATRIBUIDO` ou `ENCERRADO` |
| 503 | Serviço de Utilizadores indisponível e o utilizador não está na cache |

## 4. Serviço de Utilizadores (porta 2101)

| Endpoint | Descrição |
|---|---|
| `POST /users` | Cria utilizador: `name`, `email`, `role` (por omissão `CAMPUS_USER`). 201, ou 409 se o email já existir |
| `GET /users` | Lista os utilizadores |
| `GET /users/{id}` | Detalhe (`id`, `name`, `email`, `role`). 404 se não existir. **Usado pelo Serviço de Incidentes** |
| `GET /health` | Estado do serviço |

## 5. Serviço de Notificações (portas 2103 e 2104)

| Endpoint | Descrição |
|---|---|
| `GET /notifications` | Lista o histórico de notificações |
| `GET /notifications?incidentId=...` | Filtra por incidente |
| `GET /health` | Estado do serviço |

## 6. Como o Serviço de Incidentes usa o de Utilizadores

Em cada pedido que leva `X-User-Id`, chama `GET /users/{id}` para validar o utilizador e obter o papel.

- Timeout de 2 s por tentativa, 3 tentativas com espera crescente (0,3 s, 0,6 s), no máximo 5 s no total.
- Depois de falhar, não volta a tentar durante 15 s (circuit breaker).
- Modo de recurso: utilizadores já consultados ficam em cache 10 minutos e continuam a ser aceites com o serviço em baixo. Utilizadores desconhecidos recebem 503.

## Pontos em aberto

1. Confirmar com a Nadia o formato de erro comum (`{"detail": "..."}`) também no Serviço de Notificações.
2. Confirmar a tabela de permissões por papel (secção 3).
3. Confirmar os campos que o Serviço de Notificações devolve em `GET /notifications` (hoje: `id`, `event_id`, `event_type`, `incident_id`, `version`, `message`, `created_at`, em snake_case, ao contrário do Serviço de Incidentes, que usa camelCase).