"""Visão LIST: uma linha por sessão + cabeçalho de colunas.

    AI        STATUS      PROJECT              TIME
    CLAUDE    ◐ WORKING   telegram-downloader  04:32

TIME = há quanto tempo a sessão está NESTE estado (mesmo contador dos cards).
"""

from __future__ import annotations

from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual import events
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from ..format import DASH, ellipsize, fmt_timer
from ..models import Session, Status
from ..theme import colors
from .session_card import SessionCard, timer_style
from .status_light import StatusLight


class ListHeader(Widget):
    """TERMINAL  STATUS  PROJECT  AGENTS  TIME — as mesmas colunas das linhas.

    Com dados reais a primeira coluna é o terminal; no mock, a IA — é o mesmo
    campo, e o cabeçalho segue o que está sendo mostrado.
    """

    def compose(self):
        yield Static("", classes="marker")
        yield Static("", classes="cell name", id="list-name-title")
        yield Static("STATUS", classes="cell status")
        yield Static("PROJECT", classes="cell project")
        yield Static("AGENTS", classes="cell agents")
        yield Static("TIME", classes="cell time")

    def on_mount(self) -> None:
        self.watch(self.app, "version", lambda _: self.sync())
        self.sync()

    def sync(self) -> None:
        real = any(s.key for s in self.app.store.sessions)
        self.query_one("#list-name-title", Static).update("TERMINAL" if real else "AI")


class SessionRow(Horizontal):
    selected = False

    def __init__(self, session: Session) -> None:
        super().__init__(id=f"row-{session.id}")
        self.session = session
        self._marker = Static("", classes="marker")
        self._name = Static("", classes="cell name")
        self._light = StatusLight(session.status, classes="cell status")
        self._project = Static("", classes="cell project")
        self._agents = Static("", classes="cell agents")
        self._time = Static("", classes="cell time")

    def compose(self):
        yield self._marker
        yield self._name
        yield self._light
        yield self._project
        yield self._agents
        yield self._time

    def on_mount(self) -> None:
        self.watch(self.app, "tick", lambda _: self.sync())
        self.watch(self.app, "version", lambda _: self.sync())
        self.sync()

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self.sync()

    def sync(self) -> None:
        s = self.session
        now = datetime.now()
        seconds = max(0, int(s.in_status(now).total_seconds()))
        dead = not s.online

        self._light.status = s.status
        for status in Status:
            self.set_class(status is s.status, status.css)
        self.set_class(self.selected, "-selected")

        self._marker.update(Text("▶" if self.selected else " ", Style(color=colors().cyan, bold=True)))
        name_color = colors().cyan if self.selected else (colors().ghost if dead else colors().text)
        self._name.update(
            Text(ellipsize(s.terminal or s.short, 11), Style(color=name_color, bold=True))
        )
        self._agents.update(self._agents_text())
        self._project.update(Text(DASH if dead else s.project, Style(color=colors().ghost if dead else colors().text2)))
        self._time.update(
            Text(
                DASH if dead else fmt_timer(s.in_status(now)),
                Style.parse(colors().ghost if dead else timer_style(s.status, seconds)),
                justify="right",
            )
        )

    def _agents_text(self) -> Text:
        """`◐ claude ● codex` — o mesmo resumo do card, numa linha só."""
        s = self.session
        out = Text(no_wrap=True, overflow="ellipsis")
        if not s.agents:
            out.append(DASH, Style(color=colors().ghost))
            return out
        for i, agent in enumerate(s.agents):
            if i:
                out.append(" ")
            out.append(agent.status.symbol, Style(color=agent.status.color))
            out.append(" " + agent.label, Style(color=colors().text2))
        return out

    def on_click(self, event: events.Click) -> None:
        self.post_message(SessionCard.Picked(self.session.id, open=event.chain >= 2))
