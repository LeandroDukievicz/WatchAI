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
carcaça de contorno **cyan**, sem fundo próprio (o card aparece através dela) e
três lâmpadas. A lâmpada acesa
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
LAMP_RIM_TOP = ("▗", "▖")  # as pontas cortadas: é aqui que mora a borda do neon
LAMP_RIM_BOTTOM = ("▝", "▘")
LAMP_CORE = "██"
LAMP_SMALL = " ● "

CAP_TOP = "╭──────╮"
CAP_BOTTOM = "╰──────╯"
SMALL_CAP_TOP = "╭─────╮"
SMALL_CAP_BOTTOM = "╰─────╯"
WALL = "│"
PAD = " "  # a célula entre a parede e a bola, quando a lâmpada está apagada

# Acesa, essa célula vira brilho — e o brilho usa **o mesmo quadrante** da ponta
# da bola naquela linha. Assim ele acompanha a silhueta: na linha de cima a bola
# só existe na metade de baixo, e o halo também. Um meio-bloco inteiro ali
# criaria uma barra separada da bola por um vão (que é o canto cortado dela).

# Quanto do "apagado" da paleta cada caso usa (1.0 = o padrão dela).
DIM = 1.0
DIM_OFFLINE = 0.45
HOUSING_OFFLINE = 0.25

# As camadas do neon, do centro para fora: miolo na cor cheia, ponta cortada
# (RIM), o meio-bloco que encosta na bola (HUG) e o tingido de fundo que sobra
# na célula (GLOW).
RIM = 0.62
HUG = 0.45
GLOW = 0.16
GLOW_LIGHT = 0.26  # no branco, um tingido fraco não aparece

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

    def _lamp_styles(self, index: int, lit: int | None) -> tuple[Style, Style]:
        """(miolo, ponta) da lâmpada. Sem fundo próprio: o card aparece atrás,
        e é isso que deixa as pontas cortadas cortarem de verdade.

        Acesa, a ponta vem num tom intermediário — a borda difusa do neon.
        """
        paleta = colors()
        color = lamp_colors()[index]
        if index == lit:
            return (
                Style(color=color, bold=True),
                Style(color=blend(color, paleta.bg, RIM)),
            )
        forca = DIM_OFFLINE if self.status is Status.OFFLINE else DIM
        apagada = Style(color=paleta.off(color, forca))
        return apagada, apagada

    def _pad_style(self, index: int, lit: int | None) -> Style:
        """As células ao lado da bola: na acesa, elas são o brilho que escapa."""
        if index != lit:
            return Style()
        paleta = colors()
        cor = lamp_colors()[index]
        brilho = GLOW if paleta.dark else GLOW_LIGHT
        return Style(
            color=blend(cor, paleta.bg, HUG),
            bgcolor=blend(cor, paleta.bg, brilho),
        )

    def _housing_style(self) -> Style:
        """A carcaça é cyan, como no ícone; OFFLINE a apaga."""
        cor = colors().cyan
        if self.status is Status.OFFLINE:
            cor = fade(cor, HOUSING_OFFLINE)
        return Style(color=cor)

    def _wall_style(self) -> Style:
        """Parede: só o contorno cyan, sem fundo."""
        return self._housing_style()

    def render(self) -> Text:
        lit = self.lit_lamp()
        housing = self._housing_style()
        parede = self._wall_style()
        pequeno = self.small
        topo = SMALL_CAP_TOP if pequeno else CAP_TOP
        base = SMALL_CAP_BOTTOM if pequeno else CAP_BOTTOM
        linhas = (LAMP_SMALL,) if pequeno else (LAMP_RIM_TOP, LAMP_RIM_BOTTOM)

        out = Text(no_wrap=True)
        out.append(topo, housing)
        for index in range(LAMPS):
            miolo, ponta = self._lamp_styles(index, lit)
            halo = self._pad_style(index, lit)
            for pontas in linhas:
                out.append("\n")
                aceso = index == lit
                esquerda, direita = (PAD, PAD) if pequeno else pontas
                out.append(WALL, parede)
                out.append(esquerda if aceso and not pequeno else PAD, halo)
                if pequeno:
                    out.append(LAMP_SMALL, miolo)
                else:
                    out.append(esquerda, ponta)
                    out.append(LAMP_CORE, miolo)
                    out.append(direita, ponta)
                out.append(direita if aceso and not pequeno else PAD, halo)
                out.append(WALL, parede)
        out.append("\n")
        out.append(base, housing)
        return out


__all__ = ["TrafficLight"]
