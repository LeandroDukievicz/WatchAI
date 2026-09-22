"""HELP — modal centralizado com os atalhos."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ..theme import colors

HELP_KEYS = [
    ("↑ ↓", "select session"),
    ("← →", "navigate cards"),
    ("ENTER", "session details"),
    ("⇧A", "go to the session window"),
    ("TAB", "change panel"),
    ("T", "theme picker"),
    ("V", "cards / list view"),
    ("R", "refresh (mock: next change)"),
    ("B", "beep (on/off)"),
    ("N", "system notification (on/off)"),
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
            out.append(key.ljust(8), Style(color=colors().cyan, bold=True))
            out.append(desc + "\n", Style(color=colors().text))
        out.append("\n")
        out.append("ESC".ljust(8), Style(color=colors().cyan, bold=True))
        out.append("close", Style(color=colors().muted))
        return out

    def action_close(self) -> None:
        self.dismiss(None)
