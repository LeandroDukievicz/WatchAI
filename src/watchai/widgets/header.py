"""Cabeçalho compacto: título na borda + resumo global + relógio.

    ╭─ ◆ WatchAI  SESSION MONITOR ───────────────────────────────────────╮
    │ ACTIVE 05 │ ◐ WORKING 01  ● READY 01  ◆ INPUT 01  ...      17:42:08 │
    ╰─────────────────────────────────────────────────────────────────────╯

Zeros ficam apagados; só o que existe ganha cor. O resumo escolhe a variante
mais rica que cabe na largura (com labels → só símbolo + contagem).
"""

from __future__ import annotations

from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual.widget import Widget

from ..format import fmt_clock
from ..models import SUMMARY_ORDER, Status
from ..theme import CYAN, GHOST, LINE_HI, MUTED, TEXT


class AppHeader(Widget):
    DEFAULT_CSS = "AppHeader { height: 3; }"

    def on_mount(self) -> None:
        self.border_title = self._title()
        self.watch(self.app, "version", lambda _: self.refresh())
        self.watch(self.app, "tick", lambda _: self.refresh())

    def on_resize(self) -> None:
        self.border_title = self._title()

    def _title(self) -> Text:
        title = Text(no_wrap=True)
        title.append("◆ ", Style(color=CYAN))
        title.append("WatchAI", Style(color=CYAN, bold=True))
        if self.size.width >= 48:
            title.append("  SESSION MONITOR", Style(color=MUTED))
        return title

    def _chips(self, full: bool) -> Text:
        counts = self.app.store.counts()
        out = Text(no_wrap=True)
        first = True
        for status in SUMMARY_ORDER:
            n = counts[status]
            if status is Status.STARTING and n == 0:
                continue  # transitório: só aparece quando existe
            if not first:
                out.append("  " if full else " ")
            first = False
            lit = n > 0
            color = status.color if lit else GHOST
            out.append(status.symbol, Style(color=color))
            if full:
                out.append(f" {status.label} ", Style(color=MUTED if lit else GHOST))
            else:
                out.append(" ")
            out.append(f"{n:02d}" if full else str(n), Style(color=color, bold=lit and status.attention))
        return out

    def render(self) -> Text:
        store = self.app.store
        width = self.size.width
        clock = fmt_clock(datetime.now())

        active = Text(no_wrap=True)
        active.append("ACTIVE ", Style(color=MUTED))
        active.append(f"{store.active:02d}", Style(color=TEXT, bold=True))
        sep = Text(" │ ", Style(color=LINE_HI))

        for full in (True, False):
            left = Text(no_wrap=True)
            left.append_text(active)
            left.append_text(sep)
            left.append_text(self._chips(full))
            if left.cell_len + len(clock) + 2 <= width:
                break
        else:
            left = self._chips(False)  # último recurso: só os chips

        gap = max(1, width - left.cell_len - len(clock))
        if left.cell_len + gap + len(clock) > width:
            return left  # sem espaço para o relógio
        left.append(" " * gap)
        left.append(clock, Style(color=MUTED))
        return left
