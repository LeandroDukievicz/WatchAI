"""Breakpoints responsivos do dashboard.

Duas escadas, porque a janela encolhe em dois eixos. A **largura** decide
quantas colunas de cards cabem; a **altura** decide o tamanho do card — não
adianta um semáforo de 11 linhas numa área de 7, o card simplesmente não
aparece. Encolhendo, o card vai perdendo o que é secundário até sobrar o que se
lê sem ler: o semáforo e o nome.
"""

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


class CardMode(Enum):
    """(classe CSS, altura do card em linhas) — do maior para o menor."""

    FULL = ("full", 13, "big")  # semáforo grande + estado, agentes, atividade, tempo
    SHORT = ("short", 7, "small")  # o mesmo texto, com o semáforo pequeno
    COMPACT = ("compact", 5, "small")  # sem caixa: nome + agentes/projeto + semáforo
    MICRO = ("micro", 1, "row")  # uma linha: nome + as três lâmpadas deitadas

    def __init__(self, css: str, height: int, light: str) -> None:
        self.css = css
        self.height = height
        self.light = light

    @property
    def boxed(self) -> bool:
        """Tem caixa em volta (e, portanto, título e rodapé na borda)."""
        return self in (CardMode.FULL, CardMode.SHORT)

    @property
    def big_light(self) -> bool:
        return self is CardMode.FULL


# Larguras em que o card deixa de caber inteiro.
MICRO_WIDTH = 34
COMPACT_WIDTH = 60


def card_mode(width: int, area_height: int) -> CardMode:
    """O formato do card para esta janela.

    A altura entra na conta porque um card mais alto que a área de sessões não
    aparece — ele fica todo fora da tela, e o usuário vê um painel vazio.
    """
    if width < MICRO_WIDTH or area_height < CardMode.COMPACT.height:
        return CardMode.MICRO
    if width < COMPACT_WIDTH or area_height < CardMode.SHORT.height:
        return CardMode.COMPACT
    if area_height < CardMode.FULL.height:
        return CardMode.SHORT
    return CardMode.FULL


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
