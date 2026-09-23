"""Modelo de dados: estados, sessões e eventos.

Cada `Status` carrega TUDO que a UI precisa para se representar de forma
consistente: label, cor, símbolo e prioridade de atenção. Nenhum widget deve
hardcodar cor/símbolo de estado — sempre consultar o enum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..theme import colors


class Status(Enum):
    """Cada estado guarda a *vaga* de cor na paleta, não a cor em si — é o que
    permite trocar de tema sem tocar em widget nenhum."""

    #          label       vaga na paleta  símbolo  atenção
    READY = ("READY", "green", "●", True)  # terminou; pronta p/ nova instrução
    WORKING = ("WORKING", "cyan", "◐", False)  # executando (símbolo animado)
    WAITING = ("WAITING", "yellow", "◇", False)  # esperando processo externo
    INPUT = ("INPUT", "magenta", "◆", True)  # esperando ação do usuário
    ERROR = ("ERROR", "red", "▲", True)  # problema detectado
    OFFLINE = ("OFFLINE", "ghost", "○", False)  # terminal fechado
    STARTING = ("STARTING", "cyan2", "◌", False)  # acabou de iniciar

    def __init__(self, label: str, slot: str, symbol: str, attention: bool) -> None:
        self.label = label
        self.slot = slot
        self.symbol = symbol
        self.attention = attention

    @property
    def color(self) -> str:
        """A cor deste estado na paleta ativa, resolvida agora."""
        return getattr(colors(), self.slot)

    @property
    def css(self) -> str:
        """Nome da classe CSS: '-ready', '-working', ..."""
        return f"-{self.name.lower()}"


# Sessão encerrada — aba fechada ou agente finalizado: o card fica, avisa que
# vai sair, e sai. Você precisa poder ver que ela terminou mesmo tendo saído da
# frente do computador; depois disso, é só ocupar espaço.
AVISO_FECHADO = timedelta(minutes=5)
REMOCAO_FECHADO = timedelta(minutes=7)

# Ordem de exibição no resumo global (posições estáveis; STARTING só aparece
# quando existe)
SUMMARY_ORDER = (
    Status.WORKING,
    Status.READY,
    Status.INPUT,
    Status.WAITING,
    Status.ERROR,
    Status.OFFLINE,
    Status.STARTING,
)

# Um terminal tem vários agentes: o estado do card é o do agente que mais pede
# você. ERROR e INPUT na frente porque param o seu trabalho; READY antes de
# WORKING porque "terminou" é a notícia, "ainda trabalhando" é o normal.
PRIORIDADE = (
    Status.ERROR,
    Status.INPUT,
    Status.READY,
    Status.WAITING,
    Status.WORKING,
    Status.STARTING,
    Status.OFFLINE,
)


def agregar(estados) -> Status:
    """O estado que representa um conjunto de agentes."""
    estados = set(estados)
    if not estados:
        return Status.IDLE
    return next(s for s in PRIORIDADE if s in estados)


def ordenar(sessions, por_atencao: bool) -> list["Session"]:
    """A ordem dos cards na tela.

    O padrão é a de **descoberta**, e é de propósito: card que muda de lugar
    sozinho desfaz a memória visual — você aprende onde cada sessão fica e passa
    a olhar direto para lá, sem ler.

    Por atenção, quem precisa de você sobe ao topo, o que compensa quando há
    sessões demais para varrer com o olho. Dentro do mesmo estado a ordem de
    descoberta continua valendo, para o movimento ser o menor possível.
    """
    if not por_atencao:
        return list(sessions)
    posicao = {status: i for i, status in enumerate(PRIORIDADE)}
    return sorted(sessions, key=lambda s: (posicao.get(s.status, len(posicao)), s.id))


@dataclass
class Agent:
    """Um agente de IA rodando dentro de um terminal."""

    pid: int
    kind: str  # "claude", "codex", ...
    label: str  # como aparece no card
    status: Status
    activity: str
    started_at: datetime
    status_since: datetime

    def in_status(self, now: datetime) -> timedelta:
        return now - self.status_since


@dataclass
class Session:
    """Um **terminal**: é o card. Os agentes que rodam nele vivem em `agents`.

    No protótipo (`--mock`) cada card é uma IA sem agentes dentro; na detecção
    real o card é a aba do terminal e `agents` lista o que está rodando ali.
    """

    id: int
    name: str  # título do card: o projeto, ou a IA no mock
    short: str  # versão curta, usada no EVENT STREAM
    status: Status
    project: str
    directory: str
    pid: int
    started_at: datetime
    status_since: datetime
    activity: str
    agents: list["Agent"] = field(default_factory=list)
    key: str = ""  # identidade estável: tty, ou shell no Windows
    terminal: str = ""  # rótulo curto: "pts/10", "pwsh #4312"
    tty: str = ""  # caminho do terminal, quando existe: "/dev/pts/10"
    window_pid: int | None = None  # processo dono da janela (o emulador)
    window_app: str = ""  # nome dele, para achar o app no D-Bus
    closed_at: datetime | None = None  # quando o terminal sumiu

    @property
    def online(self) -> bool:
        return self.status is not Status.OFFLINE

    @property
    def badge(self) -> str:
        """O que vai no canto do card: o terminal, ou o número no mock."""
        return self.terminal or self.number

    def closed_for(self, now: datetime) -> timedelta | None:
        return None if self.closed_at is None else now - self.closed_at

    def closing_in(self, now: datetime) -> timedelta | None:
        """Quanto falta para o card sumir — só depois do aviso, senão None."""
        fechado = self.closed_for(now)
        if fechado is None or fechado < AVISO_FECHADO:
            return None
        return max(timedelta(0), REMOCAO_FECHADO - fechado)

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
