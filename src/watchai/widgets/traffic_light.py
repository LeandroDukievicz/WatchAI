"""TrafficLight — o semáforo no canto direito do card.

É a leitura "de longe": antes de ler qualquer texto, a lâmpada acesa já diz se
a sessão está rodando, pronta ou com problema.

    ╭───╮
    │ ● │   vermelha · ERROR
    │ ● │   amarela   · WORKING, WAITING, STARTING e INPUT (piscando)
    │ ● │   verde     · READY
    ╰───╯

Como num semáforo de verdade, as lâmpadas apagadas não somem: ficam num tom
bem escuro da própria cor. OFFLINE apaga as três e escurece também a carcaça.

INPUT é o único estado que pisca (1 s aceso / 1 s apagado, guiado pelo `tick`
do app): é o estado que depende de você voltar.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from ..models import Status
from ..theme import GREEN, LINE_HI, RED, YELLOW, fade

WIDTH = 5
HEIGHT = 5

LAMP = "●"
CAP_TOP = "╭───╮"
CAP_BOTTOM = "╰───╯"
WALL_LEFT = "│ "
WALL_RIGHT = " │"

# Brilho das lâmpadas apagadas (0.0 = some no fundo, 1.0 = cor cheia).
DIM = 0.16
DIM_OFFLINE = 0.07
HOUSING_OFFLINE = 0.25

RED_LAMP, AMBER_LAMP, GREEN_LAMP = 0, 1, 2
COLORS = (RED, YELLOW, GREEN)

# Estado -> lâmpada acesa (ausente = nenhuma acesa).
LIT: dict[Status, int] = {
    Status.ERROR: RED_LAMP,
    Status.WORKING: AMBER_LAMP,
    Status.WAITING: AMBER_LAMP,
    Status.STARTING: AMBER_LAMP,
    Status.INPUT: AMBER_LAMP,
    Status.READY: GREEN_LAMP,
}

BLINKING = {Status.INPUT}
BLINK_TICKS = 2  # tick do app = 0,5 s -> 1 s aceso, 1 s apagado


class TrafficLight(Widget):
    DEFAULT_CSS = f"""
    TrafficLight {{ width: {WIDTH}; height: {HEIGHT}; }}
    """

    status: reactive[Status] = reactive(Status.OFFLINE)
    tick: reactive[int] = reactive(0)

    def __init__(self, status: Status = Status.OFFLINE, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_reactive(TrafficLight.status, status)

    def on_mount(self) -> None:
        self.watch(self.app, "tick", self._on_tick)

    def _on_tick(self, value: int) -> None:
        # Só repinta quando há o que piscar.
        if self.status in BLINKING:
            self.tick = value

    # -- desenho ---------------------------------------------------------------
    def lit_lamp(self) -> int | None:
        """Índice da lâmpada acesa agora, já considerando o piscar."""
        lamp = LIT.get(self.status)
        if lamp is None:
            return None
        if self.status in BLINKING and (self.tick // BLINK_TICKS) % 2:
            return None
        return lamp

    def _lamp_style(self, index: int, lit: int | None) -> Style:
        color = COLORS[index]
        if index == lit:
            return Style(color=color, bold=True)
        level = DIM_OFFLINE if self.status is Status.OFFLINE else DIM
        return Style(color=fade(color, level))

    def render(self) -> Text:
        lit = self.lit_lamp()
        housing = Style(
            color=fade(LINE_HI, HOUSING_OFFLINE)
            if self.status is Status.OFFLINE
            else LINE_HI
        )

        out = Text(no_wrap=True)
        out.append(CAP_TOP, housing)
        for index in range(len(COLORS)):
            out.append("\n")
            out.append(WALL_LEFT, housing)
            out.append(LAMP, self._lamp_style(index, lit))
            out.append(WALL_RIGHT, housing)
        out.append("\n")
        out.append(CAP_BOTTOM, housing)
        return out


__all__ = ["TrafficLight"]
