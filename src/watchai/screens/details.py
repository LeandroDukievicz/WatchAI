"""SESSION DETAILS — modal aberto com ENTER, fechado com ESC.

O dashboard continua visível (escurecido) atrás, então os semáforos seguem
atualizando enquanto o detalhe está aberto.
"""

from __future__ import annotations

from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ..format import DASH, ellipsize, fmt_clock, fmt_hms, fmt_timer
from ..models import Session
from ..theme import colors
from ..widgets import StatusLight, render_status
from ..widgets.session_card import timer_style, timer_text

KEY_W = 11


def _field(label: str, value: str, value_style: str = "") -> Text:
    row = Text(no_wrap=True, overflow="ellipsis")
    row.append(label.ljust(KEY_W), Style(color=colors().muted))
    row.append(value, Style.parse(value_style or colors().text))
    return row


class DetailsScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Back", show=False),
        Binding("left,h", "step(-1)", "Prev", show=False),
        Binding("right,l", "step(1)", "Next", show=False),
    ]

    def __init__(self, session_id: int) -> None:
        super().__init__()
        self.session_id = session_id

    @property
    def session(self) -> Session:
        store = self.app.store
        return store.get(self.session_id) or store.sessions[0]

    def compose(self):
        with Vertical(id="details"):
            yield Static("", id="d-name")
            with Horizontal(id="d-status-row", classes="d-row"):
                yield Static("STATUS".ljust(KEY_W), classes="d-key")
                yield StatusLight(self.session.status, id="d-light")
            yield Static("", id="d-fields")
            yield Static("AGENTS", classes="d-section", id="d-agents-title")
            yield Static("", id="d-agents")
            yield Static("CURRENT ACTIVITY", classes="d-section")
            yield Static("", id="d-activity")
            yield Static("EVENTS", classes="d-section")
            yield Static("", id="d-events")
            yield Static("", id="d-hint")

    def on_mount(self) -> None:
        self.query_one("#details").border_title = "SESSION DETAILS"
        self.watch(self.app, "tick", lambda _: self.sync())
        self.watch(self.app, "version", lambda _: self.sync())
        self.sync()

    def on_resize(self) -> None:
        self.sync()

    # -- conteúdo ---------------------------------------------------------------
    def sync(self) -> None:
        s = self.session
        now = datetime.now()
        dead = not s.online
        seconds = max(0, int(s.in_status(now).total_seconds()))

        self.query_one("#d-name", Static).update(
            Text(s.name, Style(color=colors().ghost if dead else colors().text, bold=True))
        )
        light = self.query_one("#d-light", StatusLight)
        light.status = s.status
        light.set_suffix(
            f"{timer_text(s.status, seconds)}  ·  since {fmt_clock(s.status_since)}",
            timer_style(s.status, seconds),
        )

        fields = Text(no_wrap=True, overflow="ellipsis")
        rows = [
            _field("SESSION", s.number + (f"   {s.terminal}" if s.terminal else "")),
            _field("PID", DASH if dead else str(s.pid)),
            _field("PROJECT", DASH if dead else s.project),
            _field("DIRECTORY", DASH if dead else s.directory, colors().text2),
            _field("STARTED", DASH if dead else fmt_clock(s.started_at)),
            _field("ELAPSED", DASH if dead else fmt_hms(s.elapsed(now)), colors().muted),
        ]
        for i, row in enumerate(rows):
            if i:
                fields.append("\n")
            fields.append_text(row)
        self.query_one("#d-fields", Static).update(fields)

        agentes = Text(no_wrap=True, overflow="ellipsis")
        for i, agent in enumerate(s.agents):
            if i:
                agentes.append("\n")
            agentes.append(agent.label.ljust(KEY_W), Style(color=colors().text))
            estado = render_status(agent.status, self.app.tick)
            agentes.append_text(estado)
            agentes.append(" " * max(1, 11 - estado.cell_len))  # colunas alinhadas
            agentes.append(
                f"pid {str(agent.pid).ljust(8)} {fmt_timer(agent.in_status(now)).rjust(6)}  ",
                Style(color=colors().muted),
            )
            agentes.append(ellipsize(agent.activity, 26), Style(color=colors().text2))
        if not s.agents:
            agentes.append(
                DASH + ("  terminal closed" if dead else "  no agent running"),
                Style(color=colors().ghost),
            )
        self.query_one("#d-agents", Static).update(agentes)
        mostra_agentes = bool(s.key)
        self.query_one("#d-agents-title").display = mostra_agentes
        self.query_one("#d-agents").display = mostra_agentes

        self.query_one("#d-activity", Static).update(
            Text(s.activity, Style(color=colors().ghost if dead else colors().text))
        )

        events = self.app.store.events_for(s.id, 4)
        width = max(20, self.query_one("#d-events").size.width)
        ev_text = Text(no_wrap=True, overflow="ellipsis")
        for i, ev in enumerate(events):
            if i:
                ev_text.append("\n")
            ev_text.append(fmt_clock(ev.at), Style(color=colors().gray))
            ev_text.append(" ")
            ev_text.append_text(render_status(ev.status, 0, label=False))
            ev_text.append(" ")
            ev_text.append(
                ellipsize(ev.message, width - 11),
                Style(color=colors().text if i == 0 else colors().muted),
            )
        self.query_one("#d-events", Static).update(ev_text)

        hint = Text(no_wrap=True)
        hint.append("ESC", Style(color=colors().cyan, bold=True))
        hint.append(" back", Style(color=colors().muted))
        hint.append("   ")
        hint.append("←→", Style(color=colors().cyan, bold=True))
        hint.append(" prev/next session", Style(color=colors().muted))
        self.query_one("#d-hint", Static).update(hint)

    # -- ações ------------------------------------------------------------------
    def action_close(self) -> None:
        self.dismiss(None)

    def action_step(self, delta: int) -> None:
        sessions = self.app.store.sessions
        idx = next((i for i, s in enumerate(sessions) if s.id == self.session_id), 0)
        self.session_id = sessions[(idx + delta) % len(sessions)].id
        # mantém a seleção do dashboard alinhada com o que está aberto
        dash = self.app.screen_stack[-2] if len(self.app.screen_stack) > 1 else None
        if dash is not None and hasattr(dash, "select_session"):
            dash.select_session(self.session_id)
        self.sync()
