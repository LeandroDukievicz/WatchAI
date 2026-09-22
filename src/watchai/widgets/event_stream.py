"""EVENT STREAM — painel compacto com os últimos eventos (3 a 6 linhas).

    17:42:01 ● CODEX     READY    task completed
    17:41:54 ◐ CLAUDE    WORKING  generating files

Mais novo em cima. Com o painel em foco (TAB), ↑↓ rolam pelo histórico.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from ..format import ellipsize, fmt_clock
from ..models import SessionEvent, Status
from ..theme import colors
from .status_light import render_status

NAME_W = 8  # "OPENCODE"
STATUS_W = 8  # "STARTING"


class EventStream(Widget):
    DEFAULT_CSS = """
    EventStream { height: 1fr; min-height: 4; }
    """

    focused_panel: reactive[bool] = reactive(False)
    offset: reactive[int] = reactive(0)

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.border_title = "EVENT STREAM"

    def on_mount(self) -> None:
        # Só `version`: nada aqui é animado (os símbolos são desenhados com
        # tick=0), então repintar a cada tick seria trabalho jogado fora — e
        # este painel agora ocupa toda a altura que sobra.
        self.watch(self.app, "version", lambda _: self.refresh())

    @property
    def rows(self) -> int:
        return max(1, self.size.height)

    def watch_focused_panel(self, focused: bool) -> None:
        self.set_class(focused, "-focused")
        self.border_subtitle = "↑↓ scroll" if focused else None
        if not focused:
            # Sem o foco não há como rolar de volta: voltar ao topo garante que
            # o painel nunca fique preso mostrando eventos velhos.
            self.offset = 0

    def scroll_events(self, delta: int) -> None:
        total = len(self.app.store.events)
        limit = max(0, total - self.rows)
        self.offset = max(0, min(limit, self.offset + delta))

    def render(self) -> Text:
        events: list[SessionEvent] = self.app.store.events
        width = self.size.width
        rows = self.rows
        show_status = width >= 56
        show_name = width >= 34

        visible = events[self.offset : self.offset + rows]
        out = Text(no_wrap=True, overflow="ellipsis")
        for i, ev in enumerate(visible):
            if i:
                out.append("\n")
            newest = i == 0 and self.offset == 0
            out.append(fmt_clock(ev.at), Style(color=colors().gray))
            out.append(" ")
            out.append_text(render_status(ev.status, 0, label=False))
            used = 8 + 1 + 1
            if show_name:
                out.append(" ")
                out.append(
                    ev.short.ljust(NAME_W), Style(color=colors().text, bold=newest)
                )
                used += 1 + NAME_W
            if show_status:
                out.append(" ")
                out.append(
                    ev.status.label.ljust(STATUS_W),
                    Style(color="#5E6A7D" if ev.status is Status.OFFLINE else ev.status.color),
                )
                used += 1 + STATUS_W
            out.append(" ")
            used += 1
            out.append(
                ellipsize(ev.message, max(1, width - used)),
                Style(color=colors().text if newest else colors().muted),
            )
        return out
