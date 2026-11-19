"""Demonstração das falhas do Serviço de Incidentes (cenários B1 a B4).

Pára e volta a arrancar serviços com `docker compose` e mostra o comportamento do
Serviço de Incidentes em cada passo. Usa o Docker Compose da raiz do projeto.

Uso (com tudo a correr, a partir de qualquer pasta):
    python services/incidents-service/scripts/demo-falhas-incidentes.py

Pressupõe os utilizadores do requests.http: 1 = CAMPUS_USER (Ana), 3 = ADMIN (Eva).
Demora cerca de 2 minutos. Tira as capturas de ecrã à medida que cada passo aparece.
"""
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[3]          # raiz do projeto (onde está o docker-compose.yml)
INCIDENTES = "http://localhost:2102"
UTILIZADORES = "http://localhost:2101"
NOTIFICACOES = "http://localhost:2104"
INCIDENTE = {"category": "REDE", "location": "Demo falhas", "description": "Criado pela demo",
             "priority": "MEDIA"}
resultados = []


def titulo(texto):
    print(f"\n=== {texto} ===")


def compose(*args):
    print("$ docker compose " + " ".join(args))
    subprocess.run(["docker", "compose", *args], cwd=RAIZ, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def criar_incidente(user_id):
    """Cria um incidente em nome de um utilizador e mede a demora."""
    inicio = time.perf_counter()
    r = httpx.post(f"{INCIDENTES}/incidents", json=INCIDENTE,
                   headers={"X-User-Id": str(user_id)}, timeout=20)
    return r, time.perf_counter() - inicio


def registar(nome, esperado, obtido):
    ok = esperado == obtido
    resultados.append(ok)
    print(f"  -> {nome}: esperado {esperado}, obtido {obtido}  [{'OK' if ok else 'FALHOU'}]")


def esperar(condicao, segundos, descricao):
    fim = time.time() + segundos
    while time.time() < fim:
        try:
            if condicao():
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    print(f"  (tempo esgotado a esperar por: {descricao})")
    return False


def health():
    return httpx.get(f"{INCIDENTES}/health", timeout=5).json()


def main():
    titulo("Preparação")
    try:
        print("health:", health())
    except httpx.HTTPError:
        print("O Serviço de Incidentes não responde em http://localhost:2102.")
        print("Arranca o sistema (docker compose up -d), espera que fique healthy e tenta outra vez.")
        sys.exit(1)
    r, _ = criar_incidente(1)                       # enche a cache com o utilizador 1
    registar("incidente criado (utilizador 1 fica em cache)", 201, r.status_code)
    # Utilizador novo, que o Serviço de Incidentes ainda não consultou (fora da cache)
    novo = httpx.post(f"{UTILIZADORES}/users", timeout=10,
                      json={"name": "Demo", "email": f"demo-{uuid.uuid4().hex[:8]}@ua.pt",
                            "role": "CAMPUS_USER"}).json()
    print(f"utilizador novo criado: id {novo['id']} (fora da cache)")

    titulo("B1 - Serviço de Utilizadores parado, utilizador em cache")
    compose("stop", "users-service")
    r, t = criar_incidente(1)
    print(f"  demora: {t:.1f} s (tentativas ao serviço parado antes de usar a cache)")
    registar("pedido do utilizador em cache", 201, r.status_code)

    titulo("B2 - Serviço de Utilizadores parado, utilizador desconhecido")
    r, t = criar_incidente(novo["id"])
    print(f"  demora: {t:.1f} s | resposta: {r.text}")
    registar("pedido de utilizador fora da cache", 503, r.status_code)

    titulo("B3 - Recuperação")
    compose("start", "users-service")
    print("  a esperar que o serviço volte e o circuit breaker feche (20 s)...")
    time.sleep(20)
    r, _ = criar_incidente(novo["id"])
    registar("mesmo pedido depois de recuperar", 201, r.status_code)

    titulo("B4 - RabbitMQ parado: os pedidos continuam e os eventos ficam na outbox")
    compose("stop", "rabbitmq")
    time.sleep(6)   # dá tempo ao publicador para detetar que o broker caiu
    ids = []
    for _ in range(2):
        r, _ = criar_incidente(1)
        registar("incidente criado com o broker parado", 201, r.status_code)
        ids.append(r.json()["id"])
    estado = health()
    print("  health:", estado)
    registar("pendingEvents > 0", True, estado["pendingEvents"] > 0)
    registar("broker desligado no /health", "disconnected", estado["broker"])

    compose("start", "rabbitmq")
    print("  a esperar que o broker volte e a outbox seja esvaziada (até 90 s)...")
    esperar(lambda: health()["pendingEvents"] == 0 and health()["broker"] == "connected",
            90, "pendingEvents = 0")
    estado = health()
    print("  health:", estado)
    registar("pendingEvents = 0 depois de o broker voltar", 0, estado["pendingEvents"])

    # As notificações só aparecem se o consumidor voltar a ligar-se sozinho ao broker
    for i in ids:
        encontrada = esperar(
            lambda i=i: len(httpx.get(f"{NOTIFICACOES}/notifications",
                                      params={"incidentId": i}, timeout=10).json()) >= 1,
            60, f"notificação do incidente {i}")
        registar(f"notificação do incidente {i} guardada depois de o broker voltar",
                 True, encontrada)

    titulo("Resumo")
    print(f"{sum(resultados)}/{len(resultados)} verificações OK")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()