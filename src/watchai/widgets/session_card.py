"""SessionCard — um card por sessão, com hierarquia:

    1. IA            (título na borda)
    2. STATUS        (StatusLight + há quanto tempo está nesse estado)
    3. PROJECT
    4. ACTIVITY
    5. TEMPO         (tempo total de sessão, o mais discreto)

O card decide sozinho como se renderizar conforme a largura disponível:
  * normal   → caixa arredondada com título e subtítulo na borda;
  * compact  → sem caixa (barra lateral colorida) — para terminais < 60 colunas.
Textos longos são truncados com `…`, nunca quebrados.
"""

from __future__ import annotations

from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual import events
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from ..format import DASH, ellipsize, fmt_hms, fmt_timer
from ..models import Session, Status
from ..theme import colors, fade
from .status_light import StatusLight
from .traffic_light import TrafficLight

LABEL_W = 9  # "activity " — coluna dos rótulos no card


def timer_style(status: Status, seconds: int) -> str:
    """Estilo do contador 'há quanto tempo neste estado'.

    READY / INPUT / ERROR ficam mais fortes depois de 1 min — é exatamente o
    "terminou há dois minutos e eu ainda não voltei" do briefing.
    """
    if status is Status.OFFLINE:
        return colors().ghost
    if status.attention:
        if seconds >= 60:
            return f"bold {status.color}"
        return fade(status.color, 0.72)
    return colors().muted


def timer_text(status: Status, seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    stamp = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
    return f"for {stamp}"


class CardName(Widget):
    """Linha com o nome da IA — só existe no modo compacto (sem borda)."""

    def __init__(self, card: "SessionCard") -> None:
        super().__init__()
        self.card = card

    def render(self) -> Text:
        card, s = self.card, self.card.session
        text = Text(no_wrap=True, overflow="ellipsis")
        mark = "▶ " if card.selected else "  "
        if card.selected:
            text.append(mark, Style.parse("bold #00E5FF"))
            text.append(s.short, Style.parse("bold #00E5FF"))
        else:
            text.append(mark)
            text.append(s.short, Style(color=colors().ghost if not s.online else colors().text, bold=True))
        return text


class CardBody(Widget):
    """Linhas PROJECT / ACTIVITY / ELAPSED."""

    def __init__(self, card: "SessionCard") -> None:
        super().__init__()
        self.card = card

    def _agents(self, width: int) -> Text:
        """`agents   2  ◐ claude  ● codex` — quantos rodam e o que cada um faz.

        O símbolo vem na cor do estado **daquele** agente: com dois rodando, o
        card diz num relance qual deles terminou.
        """
        s = self.card.session
        row = Text(no_wrap=True, overflow="ellipsis")
        row.append("agents".ljust(LABEL_W), Style(color=colors().muted))
        if not s.agents:
            row.append(DASH, Style(color=colors().ghost))
            return row
        row.append(str(len(s.agents)), Style(color=colors().text, bold=True))
        for agent in s.agents:
            row.append("  ")
            row.append(agent.status.symbol, Style(color=agent.status.color))
            row.append(" " + agent.label, Style(color=colors().text2))
        return row

    def _closing(self, falta, width: int) -> Text:
        """Aviso de que o card do terminal fechado está de saída."""
        row = Text(no_wrap=True, overflow="ellipsis")
        row.append("closing".ljust(LABEL_W), Style(color=colors().yellow))
        row.append(f"⚠ removing in {fmt_timer(falta)}", Style(color=colors().yellow, bold=True))
        return row

    def _row(self, label: str, value: str, style: str, width: int) -> Text:
        row = Text(no_wrap=True, overflow="ellipsis")
        row.append(label.ljust(LABEL_W), Style(color=colors().ghost if style == colors().ghost else colors().muted))
        row.append(ellipsize(value, max(1, width - LABEL_W)), Style.parse(style))
        return row

    def render(self) -> Text:
        card, s = self.card, self.card.session
        now = datetime.now()
        width = self.size.width
        dead = not s.online
        project = DASH if dead else s.project
        elapsed = DASH if dead else fmt_hms(s.elapsed(now))
        falta = s.closing_in(now)
        # O card do terminal traz os agentes onde o do mock traz o projeto: ali
        # o título já é o projeto, e quem está rodando é a notícia.
        terminal = bool(s.key)

        if card.compact:
            # Estreito: sobram o nome (em CardName) e o projeto. O estado quem
            # dá é o semáforo ao lado — ler três lâmpadas não precisa de texto.
            lines = [
                Text(
                    ellipsize(project, max(1, width)),
                    Style(color=colors().ghost if dead else colors().text2),
                )
            ]
        else:
            if falta is not None:
                primeira = self._closing(falta, width)
            elif terminal:
                primeira = self._agents(width)
            else:
                primeira = self._row(
                    "project", project, colors().ghost if dead else colors().text, width
                )
            lines = [
                primeira,
                self._row("activity", s.activity, colors().ghost if dead else colors().text2, width),
                self._row("elapsed", elapsed, colors().ghost if dead else colors().muted, width),
            ]
        out = Text(no_wrap=True, overflow="ellipsis")
        for i, line in enumerate(lines):
            if i:
                out.append("\n")
            out.append_text(line)
        return out


class SessionCard(Widget):
    """Card de uma sessão. Não é focável: a seleção é controlada pelo Dashboard.

    Layout horizontal: a coluna de texto ocupa o espaço que sobra e o semáforo
    fica fixo na direita (5 colunas). No modo compacto o semáforo não cabe e
    some — quem dá o estado ali é a barra lateral colorida.
    """

    class Picked(Message):
        def __init__(self, session_id: int, open: bool = False) -> None:
            super().__init__()
            self.session_id = session_id
            self.open = open

    selected: reactive[bool] = reactive(False)
    compact: reactive[bool] = reactive(False)

    def __init__(self, session: Session) -> None:
        super().__init__(id=f"card-{session.id}")
        self.session = session
        self._name = CardName(self)
        self._light = StatusLight(session.status, classes="card-light")
        self._body = CardBody(self)
        self._traffic = TrafficLight(session.status)

    # -- composição ---------------------------------------------------------
    def compose(self):
        with Vertical(classes="card-main"):
            yield self._name
            yield self._light
            yield self._body
        yield self._traffic

    def on_mount(self) -> None:
        self.watch(self.app, "tick", lambda _: self.sync())
        self.watch(self.app, "version", lambda _: self.sync())
        self.sync()

    def watch_selected(self) -> None:
        self.sync()

    def watch_compact(self) -> None:
        self.sync()

    # -- sincronização com o modelo ----------------------------------------
    def sync(self) -> None:
        s = self.session
        seconds = max(0, int(s.in_status(datetime.now()).total_seconds()))

        self._light.status = s.status
        self._light.set_suffix(timer_text(s.status, seconds), timer_style(s.status, seconds))
        self._traffic.status = s.status

        for status in Status:
            self.set_class(status is s.status, status.css)
        self.set_class(self.selected, "-selected")
        self.set_class(self.compact, "-compact")

        if self.compact:
            self.border_title = None
            self.border_subtitle = None
        else:
            self.border_title = ("▶ " if self.selected else "") + s.name
            self.border_subtitle = s.badge

        self._name.refresh()
        self._body.refresh()

    # -- mouse ---------------------------------------------------------------
    def on_click(self, event: events.Click) -> None:
        self.post_message(self.Picked(self.session.id, open=event.chain >= 2))
