"""Breakpoints responsivos do dashboard."""

from __future__ import annotations

from enum import Enum


class Layout(Enum):
    """(nome da classe CSS, colunas de cards, largura mínima em colunas)"""

    LARGE = ("large", 3, 130)
    MEDIUM = ("medium", 2, 90)
    SMALL = ("small", 1, 60)
    TINY = ("tiny", 1, 0)

    def __init__(self, css: str, columns: int, min_width: int) -> None:
        self.css = css
        self.columns = columns
        self.min_width = min_width

    @property
    def compact(self) -> bool:
        """Cards em formato compacto (sem caixa) — só no menor breakpoint."""
        return self is Layout.TINY


def layout_for(width: int) -> Layout:
    for layout in (Layout.LARGE, Layout.MEDIUM, Layout.SMALL):
        if width >= layout.min_width:
            return layout
    return Layout.TINY


# Linhas que nunca pertencem à área de sessões: header (3) + título (1) + keybar (1).
CHROME_ROWS = 5
# Piso do EVENT STREAM: borda + 6 eventos + borda. A área de sessões pode crescer
# até o que sobrar disso — passou, ela rola em vez de empurrar o stream da tela.
EVENTS_MIN_ROWS = 8
SESSIONS_MIN_ROWS = 4


def sessions_max_height(terminal_height: int) -> int:
    """Teto da área de sessões para o EVENT STREAM nunca sumir."""
    return max(SESSIONS_MIN_ROWS, terminal_height - CHROME_ROWS - EVENTS_MIN_ROWS)
