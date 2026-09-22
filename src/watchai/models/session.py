"""Modelo de dados: estados, sessões e eventos.

Cada `Status` carrega TUDO que a UI precisa para se representar de forma
consistente: label, cor, símbolo e prioridade de atenção. Nenhum widget deve
hardcodar cor/símbolo de estado — sempre consultar o enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from ..theme import CYAN_2, GHOST, GREEN, MAGENTA, RED, YELLOW, CYAN


class Status(Enum):
    #          label       cor      símbolo  atenção
    READY = ("READY", GREEN, "●", True)  # terminou; pronta p/ nova instrução
    WORKING = ("WORKING", CYAN, "◐", False)  # executando (símbolo animado)
    WAITING = ("WAITING", YELLOW, "◇", False)  # esperando processo externo
    INPUT = ("INPUT", MAGENTA, "◆", True)  # esperando ação do usuário
    ERROR = ("ERROR", RED, "▲", True)  # problema detectado
    OFFLINE = ("OFFLINE", GHOST, "○", False)  # sessão encerrada
    STARTING = ("STARTING", CYAN_2, "◌", False)  # acabou de iniciar

    def __init__(self, label: str, color: str, symbol: str, attention: bool) -> None:
        self.label = label
        self.color = color
        self.symbol = symbol
        self.attention = attention

    @property
    def css(self) -> str:
        """Nome da classe CSS: '-ready', '-working', ..."""
        return f"-{self.name.lower()}"


# Ordem de exibição no resumo global (posições estáveis; STARTING só aparece se > 0)
SUMMARY_ORDER = (
    Status.WORKING,
    Status.READY,
    Status.INPUT,
    Status.WAITING,
    Status.ERROR,
    Status.OFFLINE,
    Status.STARTING,
)


@dataclass
class Session:
    id: int
    name: str  # "CLAUDE CODE"
    short: str  # "CLAUDE"
    status: Status
    project: str
    directory: str
    pid: int
    started_at: datetime
    status_since: datetime
    activity: str

    @property
    def online(self) -> bool:
        return self.status is not Status.OFFLINE

    def elapsed(self, now: datetime) -> timedelta:
        return now - self.started_at

    def in_status(self, now: datetime) -> timedelta:
        return now - self.status_since

    @property
    def number(self) -> str:
        return f"#{self.id:02d}"


@dataclass
class SessionEvent:
    at: datetime
    session_id: int
    short: str
    status: Status
    message: str
