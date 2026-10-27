"""
Cliente do Serviço de Utilizadores (GET /users/{id}).

Tolerância a falhas:
  1. Timeout em cada tentativa (não ficamos pendurados se o users-service estiver lento).
  2. Retries com espera crescente (backoff) em erros de rede e respostas 5xx.
  3. Comportamento de recurso: se o users-service continuar em baixo, usamos o último
     resultado conhecido (cache em memória, com validade limitada). Se não houver
     cache, levantamos UsersUnavailable (a API responde 503).
"""
import logging
import time

import httpx

from app import config

log = logging.getLogger("incidents.users_client")

# user_id -> (dados do utilizador, momento em que foi obtido)
_cache: dict[int, tuple[dict, float]] = {}


class UserNotFound(Exception):
    """O utilizador não existe (404 do users-service). Não vale a pena repetir."""


class UsersUnavailable(Exception):
    """O users-service está indisponível e não há dados em cache."""


def get_user(user_id: int) -> dict:
    last_error: Exception | None = None

    for attempt in range(1, config.USERS_RETRIES + 1):
        try:
            resp = httpx.get(
                f"{config.USERS_SERVICE_URL}/users/{user_id}", timeout=config.USERS_TIMEOUT
            )
            if resp.status_code == 200:
                user = resp.json()
                _cache[user_id] = (user, time.monotonic())  # guarda para o modo de recurso
                return user
            if resp.status_code == 404:
                raise UserNotFound(user_id)
            # 5xx ou outro código inesperado: trata como falha temporária
            last_error = RuntimeError(f"users-service respondeu {resp.status_code}")
        except UserNotFound:
            raise
        except httpx.HTTPError as exc:  # timeout, ligação recusada, etc.
            last_error = exc

        log.warning("users-service falhou (tentativa %d/%d): %s",
                    attempt, config.USERS_RETRIES, last_error)
        if attempt < config.USERS_RETRIES:
            time.sleep(config.USERS_BACKOFF * 2 ** (attempt - 1))  # 0.3s, 0.6s, 1.2s...

    # Todas as tentativas falharam -> comportamento de recurso
    cached = _cache.get(user_id)
    if cached and time.monotonic() - cached[1] <= config.USERS_CACHE_TTL:
        log.error("users-service em baixo; a usar dados em cache do utilizador %s", user_id)
        return cached[0]

    log.error("users-service em baixo e sem cache para o utilizador %s: %s", user_id, last_error)
    raise UsersUnavailable(str(last_error))


def clear_cache() -> None:
    """Usado nos testes."""
    _cache.clear()
