"""Título de seção com régua: `▸ SESSIONS 06 ───────── CARDS │ LIST`.

Não é uma caixa: apenas uma linha que organiza. O painel em foco (TAB)
acende em cyan; o outro fica cinza.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from ..theme import colors


class PanelTitle(Widget):
    DEFAULT_CSS = "PanelTitle { height: 1; }"

    focused_panel: reactive[bool] = reactive(True)
    view: reactive[str] = reactive("cards")

    def on_mount(self) -> None:
        self.watch(self.app, "version", lambda _: self.refresh())

    def render(self) -> Text:
        n = len(self.app.store.sessions)
        focus = self.focused_panel
        out = Text(no_wrap=True, overflow="ellipsis")
        out.append("▸ " if focus else "  ", Style(color=colors().cyan, bold=True))
        out.append("SESSIONS", Style(color=colors().cyan if focus else colors().muted, bold=focus))
        out.append(f" {n:02d}", Style(color=colors().text if focus else colors().ghost))

        right = Text(no_wrap=True)
        for i, name in enumerate(("cards", "list")):
            if i:
                right.append(" │ ", Style(color=colors().line_hi))
            on = self.view == name
            right.append(name.upper(), Style(color=colors().cyan if on else colors().ghost, bold=on))

        rule = max(0, self.size.width - out.cell_len - right.cell_len - 2)
        out.append(" ")
        out.append("─" * rule, Style(color=colors().cyan2 if focus else colors().line))
        out.append(" ")
        out.append_text(right)
        return out
