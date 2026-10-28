"""Teste manual do users_client. Uso (dentro de services/incidents-service):
    python -m scripts.teste_users <id_existente> <id_sem_cache>
Exemplo: python -m scripts.teste_users 3 2
O <id_sem_cache> tem de existir na BD mas não ser consultado antes."""
import logging
import sys

from app import users_client

logging.basicConfig(level=logging.INFO)
existente = int(sys.argv[1]) if len(sys.argv) > 1 else 1
sem_cache = int(sys.argv[2]) if len(sys.argv) > 2 else 2

print("1) existe:", users_client.get_user(existente))

try:
    users_client.get_user(999999)
except users_client.UserNotFound:
    print("2) 404 ok (sem retries)")

input("3) Pára o serviço: docker compose stop users-service  e carrega Enter... ")

print("4) cache de recurso:", users_client.get_user(existente))

try:
    users_client.get_user(sem_cache)
except users_client.UsersUnavailable:
    print("5) sem cache -> UsersUnavailable (a API devolveria 503)")