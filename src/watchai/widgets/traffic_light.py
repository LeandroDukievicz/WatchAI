"""TrafficLight — o semáforo no canto direito do card.

É a leitura "de longe": antes de ler qualquer texto, a lâmpada acesa já diz se
a sessão está rodando, pronta ou com problema.

    ╭──────╮
    │ ▗██▖ │   vermelha · ERROR
    │ ▝██▘ │
    │ ▗██▖ │   amarela  · WORKING, WAITING, STARTING e INPUT (piscando)
    │ ▝██▘ │
    │ ▗██▖ │   verde    · READY
    │ ▝██▘ │
    ╰──────╯

Cada lâmpada ocupa **duas linhas cheias**, com as quatro pontas cortadas por
quadrantes: o que sobra é um círculo — o mais redondo que uma grade de
caracteres permite — em vez de um ponto. Em terminais estreitos entra a versão pequena (`●`, cinco linhas), que é
o que cabe.

É o mesmo semáforo do ícone do app (`assets/watchai.svg`), desenhado em texto:
carcaça de contorno **cyan**, interior escuro e três lâmpadas. A lâmpada acesa
**brilha** — cor cheia, negrito e um fundo tingido da própria cor nas três
células. É o halo que faz o semáforo ser lido antes do texto, do outro lado da
sala.

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
from ..theme import blend, colors, fade

WIDTH = 8
HEIGHT = 8

# Versão pequena, para quando não há largura nem altura (modo compacto).
SMALL_WIDTH = 7
SMALL_HEIGHT = 5

# A bola: duas linhas cheias com as quatro pontas cortadas por **quadrantes**.
# Meio-bloco (`▄`) tira metade da ponta; o quadrante (`▗`) tira três quartos —
# e é essa diferença que separa um bloco de um círculo. Em sub-células:
#
#     ..####..
#     .######.
#     .######.
#     ..####..
#
# São **4** células por 2 linhas, e a largura não é arbitrária: a célula do
# terminal é ~2x mais alta que larga, então 4 de largura por 2 de altura dá um
# quadrado — e aí o corte de um quadrante vale 25% nos dois eixos. Com 5 de
# largura o corte valeria 10% na horizontal contra 25% na vertical, e o que
# aparecia era um retângulo de cantos lascados.
LAMP_TOP = "▗██▖"
LAMP_BOTTOM = "▝██▘"
LAMP_SMALL = " ● "

CAP_TOP = "╭──────╮"
CAP_BOTTOM = "╰──────╯"
SMALL_CAP_TOP = "╭─────╮"
SMALL_CAP_BOTTOM = "╰─────╯"
WALL = "│"
PAD = " "  # a célula entre a parede e a bola: é aqui que mora o halo

# Quanto do "apagado" da paleta cada caso usa (1.0 = o padrão dela).
DIM = 1.0
DIM_OFFLINE = 0.45
HOUSING_OFFLINE = 0.25

# Fundo tingido atrás da lâmpada acesa: é daqui que vem o destaque.
GLOW = 0.22
GLOW_LIGHT = 0.34  # no branco, um tingido fraco não aparece

RED_LAMP, AMBER_LAMP, GREEN_LAMP = 0, 1, 2
LAMPS = 3


def lamp_colors() -> tuple[str, str, str]:
    """As três cores do semáforo na paleta ativa, de cima para baixo."""
    c = colors()
    return (c.red, c.yellow, c.green)

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
    TrafficLight.-small {{ width: {SMALL_WIDTH}; height: {SMALL_HEIGHT}; }}
    """

    status: reactive[Status] = reactive(Status.OFFLINE)
    tick: reactive[int] = reactive(0)
    small: reactive[bool] = reactive(False)

    def __init__(self, status: Status = Status.OFFLINE, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_reactive(TrafficLight.status, status)

    def on_mount(self) -> None:
        self.watch(self.app, "tick", self._on_tick)
        self.set_class(self.small, "-small")

    def watch_small(self, small: bool) -> None:
        if self.is_mounted:
            self.set_class(small, "-small")

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
        """A lâmpada. O fundo é sempre o interior da carcaça: é o que deixa os
        cantos cortados aparecerem e a bola ficar **redonda** — pintar o fundo
        atrás dela a transformaria num retângulo."""
        paleta = colors()
        color = lamp_colors()[index]
        dentro = self._inside()
        if index == lit:
            return Style(color=color, bgcolor=dentro, bold=True)
        forca = DIM_OFFLINE if self.status is Status.OFFLINE else DIM
        return Style(color=paleta.off(color, forca, sobre=dentro), bgcolor=dentro)

    def _pad_style(self, index: int, lit: int | None) -> Style:
        """As células ao lado da bola: no acesa, elas viram o halo."""
        dentro = self._inside()
        if index != lit:
            return Style(bgcolor=dentro)
        paleta = colors()
        brilho = GLOW if paleta.dark else GLOW_LIGHT
        return Style(bgcolor=blend(lamp_colors()[index], dentro, brilho))

    def _inside(self) -> str:
        """O fundo de dentro da carcaça — o `#080D16` do ícone, na paleta ativa."""
        return colors().bg2

    def _housing_style(self) -> Style:
        """A carcaça é cyan, como no ícone; OFFLINE a apaga."""
        cor = colors().cyan
        if self.status is Status.OFFLINE:
            cor = fade(cor, HOUSING_OFFLINE)
        return Style(color=cor)

    def _wall_style(self) -> Style:
        """Parede: contorno cyan, fundo do interior — o mesmo da lâmpada."""
        return self._housing_style() + Style(bgcolor=self._inside())

    def render(self) -> Text:
        lit = self.lit_lamp()
        housing = self._housing_style()
        parede = self._wall_style()
        pequeno = self.small
        topo = SMALL_CAP_TOP if pequeno else CAP_TOP
        base = SMALL_CAP_BOTTOM if pequeno else CAP_BOTTOM
        linhas = (LAMP_SMALL,) if pequeno else (LAMP_TOP, LAMP_BOTTOM)

        out = Text(no_wrap=True)
        out.append(topo, housing)
        for index in range(LAMPS):
            estilo = self._lamp_style(index, lit)
            halo = self._pad_style(index, lit)
            for linha in linhas:
                out.append("\n")
                out.append(WALL, parede)
                out.append(PAD, halo)
                out.append(linha, estilo)
                out.append(PAD, halo)
                out.append(WALL, parede)
        out.append("\n")
        out.append(base, housing)
        return out


__all__ = ["TrafficLight"]
