"""Cenário A6 - pedidos simultâneos sobre o mesmo incidente (controlo otimista).

Em cada ronda:
  1. cria um incidente novo (version 1);
  2. dispara ao mesmo tempo dois PUT /assign com a MESMA version (1),
     um para cada técnico;
  3. verifica que um pedido deu 200 e o outro 409, e que o incidente ficou
     com version 2 (só uma alteração entrou).

Uso (com o Docker a correr):
    python scripts/teste-concorrencia.py [URL_BASE] [N_RONDAS]
Exemplo:
    python scripts/teste-concorrencia.py http://localhost:2102 3

Pressupõe os utilizadores do requests.http: 1 = CAMPUS_USER, 2 e 4 = TECHNICIAN, 3 = ADMIN.
Precisa do pacote httpx (já está no .venv do incidents-service).
"""
import sys
import threading

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:2102"
RONDAS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
CAMPUS_USER, ADMIN, TECNICOS = 1, 3, (2, 4)


def criar_incidente():
    r = httpx.post(
        f"{BASE}/incidents",
        json={"category": "EQUIPAMENTO", "location": "Teste concorrência",
              "description": "Incidente criado pelo script A6", "priority": "MEDIA"},
        headers={"X-User-Id": str(CAMPUS_USER)}, timeout=10)
    r.raise_for_status()
    return r.json()


def atribuir(incidente, tecnico, barreira, resultados):
    """Corre numa thread: espera na barreira para largar ao mesmo tempo que a outra."""
    with httpx.Client(timeout=10) as cliente:
        barreira.wait()
        r = cliente.put(
            f"{BASE}/incidents/{incidente['id']}/assign",
            json={"technicianId": tecnico, "version": incidente["version"]},
            headers={"X-User-Id": str(ADMIN)})
    resultados[tecnico] = r.status_code


def main():
    falhas = 0
    for n in range(1, RONDAS + 1):
        inc = criar_incidente()
        barreira = threading.Barrier(len(TECNICOS))
        resultados = {}
        threads = [threading.Thread(target=atribuir, args=(inc, t, barreira, resultados))
                   for t in TECNICOS]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = httpx.get(f"{BASE}/incidents/{inc['id']}", timeout=10).json()
        codigos = sorted(resultados.values())
        ok = codigos == [200, 409] and final["version"] == 2
        falhas += 0 if ok else 1
        print(f"Ronda {n}: incidente {inc['id']} | códigos {resultados} | "
              f"version final {final['version']} | atribuído a {final['assignedTo']} | "
              f"{'OK' if ok else 'FALHOU'}")

    print(f"\n{RONDAS - falhas}/{RONDAS} rondas OK")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
