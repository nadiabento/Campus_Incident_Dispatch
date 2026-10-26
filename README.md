# Campus Incident Dispatch

Sistema distribuído de notificação de incidentes e envio de intervenções de manutenção, desenvolvido para a unidade curricular de Sistemas Distribuídos (Licenciatura em Engenharia Informática Aplicada, 2026/2027).

## Serviços

| Serviço                                | Estado             | Função                                               |
| -------------------------------------- | ------------------ | ---------------------------------------------------- |
| Utilizadores (`users-service`)         | Implementado       | Regista e consulta utilizadores e os seus papéis     |
| Incidentes (`incidents-service`)       | Em desenvolvimento | Gere incidentes e publica eventos no broker          |
| Notificações (`notifications-service`) | Em desenvolvimento | Consome eventos e guarda o histórico de notificações |

Os serviços comunicam por REST (API) e por mensagens assíncronas através do RabbitMQ. Cada serviço tem a sua própria base de dados.

## Tecnologias

- Python 3.12 e FastAPI
- SQLAlchemy e PostgreSQL 16
- RabbitMQ 3 (com consola de gestão)
- Docker e Docker Compose

## Portas

| Componente                    | Porta no PC | Porta no contentor |
| ----------------------------- | ----------- | ------------------ |
| Serviço de Utilizadores       | 2101        | 8000               |
| Serviço de Incidentes         | 2102        | 8000               |
| Serviço de Notificações       | 2103        | 8000               |
| RabbitMQ (mensagens)          | 2201        | 5672               |
| RabbitMQ (consola web)        | 2202        | 15672              |
| Base de dados de utilizadores | 2301        | 5432               |

_(Incidentes e Notificações: portas a confirmar quando forem implementados.)_

## Variáveis de configuração

Ver `.env.example`. Variáveis atuais:

| Variável                                            | Descrição                                                          |
| --------------------------------------------------- | ------------------------------------------------------------------ |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Utilizador, palavra-passe e nome da base de dados de utilizadores  |
| `DATABASE_URL`                                      | Endereço de ligação do Serviço de Utilizadores à sua base de dados |

## Ordem de arranque

O Docker Compose arranca por esta ordem:

1. RabbitMQ e bases de dados.
2. Cada serviço, apenas depois da sua base de dados estar pronta (`healthcheck`).

## Como executar

Pré-requisitos: Docker Desktop em execução e as portas acima livres.

```bash
docker compose up --build
```

Depois de arrancar:

- Documentação e testes da API de utilizadores: http://localhost:2101/docs
- Estado do serviço: http://localhost:2101/health
- Consola do RabbitMQ: http://localhost:2202 (utilizador `guest`, palavra-passe `guest`)

Para parar:

```bash
docker compose down        # mantém os dados
docker compose down -v     # apaga também os dados
```

## API do Serviço de Utilizadores

| Método | Caminho       | Descrição                                                         |
| ------ | ------------- | ----------------------------------------------------------------- |
| POST   | `/users`      | Cria um utilizador (papéis: `CAMPUS_USER`, `TECHNICIAN`, `ADMIN`) |
| GET    | `/users`      | Lista os utilizadores                                             |
| GET    | `/users/{id}` | Devolve um utilizador                                             |
| GET    | `/health`     | Verifica se o serviço está ativo                                  |

Exemplos de pedidos: ver a pasta `examples/`.

## Estrutura do repositório

```
├── docker-compose.yml
├── .env.example
├── services/
│   ├── users-service/
│   ├── incidents-service/
│   └── notifications-service/
├── infra/
├── examples/
└── scripts/
```

## Autores

- Nadia Bento
- Jessica Pereira
