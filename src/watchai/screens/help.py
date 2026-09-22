"""HELP — modal centralizado com os atalhos."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ..theme import CYAN, MUTED, TEXT

HELP_KEYS = [
    ("↑ ↓", "select session"),
    ("← →", "navigate cards"),
    ("ENTER", "session details"),
    ("TAB", "change panel"),
    ("V", "cards / list view"),
    ("R", "refresh (mock: next change)"),
    ("B", "beep on READY (on/off)"),
    ("?", "help"),
    ("Q", "quit"),
]


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,question_mark", "close", "Close", show=False),
    ]

    def compose(self):
        with Vertical(id="help"):
            yield Static(self._body(), id="help-body")

    def on_mount(self) -> None:
        self.query_one("#help").border_title = "HELP"

    def _body(self) -> Text:
        out = Text(no_wrap=True, overflow="ellipsis")
        for key, desc in HELP_KEYS:
            out.append(key.ljust(8), Style(color=CYAN, bold=True))
            out.append(desc + "\n", Style(color=TEXT))
        out.append("\n")
        out.append("ESC".ljust(8), Style(color=CYAN, bold=True))
        out.append("close", Style(color=MUTED))
        return out

    def action_close(self) -> None:
        self.dismiss(None)
