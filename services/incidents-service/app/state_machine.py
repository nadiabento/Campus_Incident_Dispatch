"""
Máquina de estados dos incidentes.

    ABERTO -> ATRIBUIDO -> EM_CURSO -> RESOLVIDO -> ENCERRADO
                 ^  |                      |
                 +--+ (reatribuir)         +--> EM_CURSO (reabrir)
"""
from enum import Enum


class Status(str, Enum):
    ABERTO = "ABERTO"
    ATRIBUIDO = "ATRIBUIDO"
    EM_CURSO = "EM_CURSO"
    RESOLVIDO = "RESOLVIDO"
    ENCERRADO = "ENCERRADO"


# estado atual -> estados para onde pode ir
TRANSITIONS: dict[Status, set[Status]] = {
    Status.ABERTO: {Status.ATRIBUIDO},
    Status.ATRIBUIDO: {Status.ATRIBUIDO, Status.EM_CURSO},  # ATRIBUIDO->ATRIBUIDO = reatribuir
    Status.EM_CURSO: {Status.RESOLVIDO},
    Status.RESOLVIDO: {Status.EM_CURSO, Status.ENCERRADO},  # EM_CURSO = reaberto
    Status.ENCERRADO: set(),                                # estado final
}


def can_transition(current: Status, target: Status) -> bool:
    return target in TRANSITIONS[current]