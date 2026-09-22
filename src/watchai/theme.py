"""Paleta e tema do WatchAI.

Fonte única das cores: o TCSS recebe estas mesmas cores como variáveis
(`$aw-cyan`, `$aw-bg`, ...) através do `Theme.variables`, e os widgets que
desenham texto com Rich importam as constantes daqui.

Se o terminal não suporta truecolor, o Textual faz o downgrade automático
para a paleta de 256 / 16 cores mais próxima.
"""

from __future__ import annotations

from functools import lru_cache

from textual.color import Color
from textual.theme import Theme

# --- Paleta base (conforme o briefing) -------------------------------------
BG = "#05070D"
BG_2 = "#080D16"
CYAN = "#00E5FF"
CYAN_2 = "#00AFC8"
MAGENTA = "#FF2BD6"
GREEN = "#39FF88"
YELLOW = "#FFD166"
RED = "#FF4D6D"
GRAY = "#657080"
TEXT = "#D8E2F0"
MUTED = "#7C8799"

# --- Derivadas (bordas e superfícies discretas) -----------------------------
TEXT_2 = "#A9B5C7"  # texto secundário (activity)
LINE = "#1A2333"  # borda neutra
LINE_HI = "#2A3850"  # borda neutra em foco/hover
GHOST = "#3A4456"  # OFFLINE: quase some no fundo
EDGE_WORKING = "#0E4652"  # WORKING: cyan bem apagado (calmo)
EDGE_WAITING = "#54472A"  # WAITING: âmbar bem apagado
TINT_SELECT = "#0B1626"  # card selecionado
TINT_GREEN = "#07170F"  # card READY
TINT_MAGENTA = "#170A1C"  # card INPUT
TINT_RED = "#1A0910"  # card ERROR
TINT_GREEN_SEL = "#0A2115"
TINT_MAGENTA_SEL = "#220E29"
TINT_RED_SEL = "#26101A"


@lru_cache(maxsize=256)
def fade(color: str, level: float, bg: str = BG) -> str:
    """Mistura `color` com o fundo. level=1.0 -> cor cheia, 0.0 -> fundo."""
    level = max(0.0, min(1.0, level))
    return Color.parse(color).blend(Color.parse(bg), 1.0 - level).hex


AI_WATCH_THEME = Theme(
    name="watchai",
    primary=CYAN,
    secondary=MAGENTA,
    accent=MAGENTA,
    success=GREEN,
    warning=YELLOW,
    error=RED,
    foreground=TEXT,
    background=BG,
    surface=BG_2,
    panel=BG_2,
    dark=True,
    variables={
        "aw-bg": BG,
        "aw-bg-2": BG_2,
        "aw-cyan": CYAN,
        "aw-cyan-2": CYAN_2,
        "aw-magenta": MAGENTA,
        "aw-green": GREEN,
        "aw-yellow": YELLOW,
        "aw-red": RED,
        "aw-gray": GRAY,
        "aw-text": TEXT,
        "aw-text-2": TEXT_2,
        "aw-muted": MUTED,
        "aw-line": LINE,
        "aw-line-hi": LINE_HI,
        "aw-ghost": GHOST,
        "aw-edge-working": EDGE_WORKING,
        "aw-edge-waiting": EDGE_WAITING,
        "aw-tint-select": TINT_SELECT,
        "aw-tint-green": TINT_GREEN,
        "aw-tint-magenta": TINT_MAGENTA,
        "aw-tint-red": TINT_RED,
        "aw-tint-green-sel": TINT_GREEN_SEL,
        "aw-tint-magenta-sel": TINT_MAGENTA_SEL,
        "aw-tint-red-sel": TINT_RED_SEL,
    },
)
