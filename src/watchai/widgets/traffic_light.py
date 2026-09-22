"""TrafficLight — o semáforo no canto direito do card.

É a leitura "de longe": antes de ler qualquer texto, a lâmpada acesa já diz se
a sessão está rodando, pronta ou com problema.

    ╭────────╮
    │ ▗▟██▙▖ │   vermelha · ERROR
    │ ██████ │
    │ ▝▜██▛▘ │
    │ ▗▟██▙▖ │   amarela  · WORKING, WAITING, STARTING e INPUT
    │ ██████ │
    │ ▝▜██▛▘ │
    │ ▗▟██▙▖ │   verde    · READY
    │ ██████ │
    │ ▝▜██▛▘ │
    ╰────────╯

Cada lâmpada é um **octógono regular** de 6 células por 3 linhas, com os quatro
cantos cortados em diagonal por quadrantes. Em terminais estreitos entra a versão pequena (`●`, cinco linhas), que é
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

WIDTH = 10
HEIGHT = 11

# Versão pequena, para quando falta altura (modo compacto).
SMALL_WIDTH = 7
SMALL_HEIGHT = 5

# Versão deitada: as três lâmpadas numa linha só. É o que cabe quando a janela
# fica minúscula — e continua dizendo o estado sem uma palavra de texto.
ROW_WIDTH = 5
ROW_HEIGHT = 1

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
# A bola: um octógono regular de 6 células por 3 linhas. Em sub-células (cada
# caractere vale 2x2), o desenho é este:
#
#     ...######...
#     .##########.
#     ############
#     ############
#     .##########.
#     ...######...
#
# 12 sub-colunas por 6 sub-linhas — e como a célula do terminal é ~2x mais alta
# que larga, isso dá 6w x 6w: um quadrado com os quatro cantos cortados em
# diagonal de verdade. Com 2 linhas só cabia **um** degrau por canto, que o olho
# lê como entalhe, não como lado do octógono.
#
# Cada linha é (ponta esquerda, miolo, ponta direita).
LAMP_ROWS = (
    ("▗", "▟██▙", "▖"),
    ("", "██████", ""),
    ("▝", "▜██▛", "▘"),
)
LAMP = "●"
LAMP_SMALL = " ● "

CAP_TOP = "╭────────╮"
CAP_BOTTOM = "╰────────╯"
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
# num tom intermediário (RIM) e o fundo tingido da célula ao lado (GLOW).
RIM = 0.62  # a ponta cortada, em tom intermediário: a borda difusa do neon
# O brilho mora **no fundo das células de canto da própria bola**: ali metade da
# célula está vazia (é o corte do octógono), e tingir esse vazio faz o halo
# seguir a forma. Nas células ao lado sobra um tingido bem mais fraco.
GLOW = 0.26
GLOW_LIGHT = 0.34  # no branco, um tingido fraco não aparece
GLOW_PAD = 0.38  # quanto do brilho sobra na célula seguinte

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
    """O semáforo em três formatos: `big` (padrão), `small` e `row` (deitado)."""

    DEFAULT_CSS = f"""
    TrafficLight {{ width: {WIDTH}; height: {HEIGHT}; }}
    TrafficLight.-small {{ width: {SMALL_WIDTH}; height: {SMALL_HEIGHT}; }}
    TrafficLight.-row {{ width: {ROW_WIDTH}; height: {ROW_HEIGHT}; }}
    """

    status: reactive[Status] = reactive(Status.OFFLINE)
    tick: reactive[int] = reactive(0)
    form: reactive[str] = reactive("big")  # "big" | "small" | "row"

    def __init__(self, status: Status = Status.OFFLINE, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_reactive(TrafficLight.status, status)

    def on_mount(self) -> None:
        self.watch(self.app, "tick", self._on_tick)
        self._apply_form()

    def watch_form(self) -> None:
        if self.is_mounted:
            self._apply_form()

    def _apply_form(self) -> None:
        self.set_class(self.form == "small", "-small")
        self.set_class(self.form == "row", "-row")

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

    def _render_row(self, lit: int | None) -> Text:
        """As três lâmpadas deitadas: `● ● ●`. Sem carcaça — nesse tamanho ela
        só roubaria colunas do nome do projeto."""
        out = Text(no_wrap=True)
        for index in range(LAMPS):
            if index:
                out.append(" ")
            miolo, _ = self._lamp_styles(index, lit)
            out.append(LAMP, miolo)
        return out

    def _lamp_styles(self, index: int, lit: int | None) -> tuple[Style, Style]:
        """(miolo, ponta) da lâmpada. Sem fundo próprio: o card aparece atrás,
        e é isso que deixa as pontas cortadas cortarem de verdade.

        Acesa, a ponta vem num tom intermediário — a borda difusa do neon.
        """
        paleta = colors()
        color = lamp_colors()[index]
        if index == lit:
            brilho = blend(color, paleta.bg, GLOW if paleta.dark else GLOW_LIGHT)
            return (
                Style(color=color, bold=True),
                # A ponta cortada: traço em tom médio sobre o vazio tingido.
                Style(color=blend(color, paleta.bg, RIM), bgcolor=brilho),
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
        brilho = (GLOW if paleta.dark else GLOW_LIGHT) * GLOW_PAD
        return Style(bgcolor=blend(cor, paleta.bg, brilho))

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
        if self.form == "row":
            return self._render_row(lit)
        housing = self._housing_style()
        parede = self._wall_style()
        pequeno = self.form == "small"

        out = Text(no_wrap=True)
        out.append(SMALL_CAP_TOP if pequeno else CAP_TOP, housing)
        for index in range(LAMPS):
            miolo, ponta = self._lamp_styles(index, lit)
            halo = self._pad_style(index, lit)
            linhas = (("", LAMP_SMALL, ""),) if pequeno else LAMP_ROWS
            for esq, centro, dir_ in linhas:
                out.append("\n")
                out.append(WALL, parede)
                out.append(PAD, halo)
                out.append(esq, ponta)
                out.append(centro, miolo)
                out.append(dir_, ponta)
                out.append(PAD, halo)
                out.append(WALL, parede)
        out.append("\n")
        out.append(SMALL_CAP_BOTTOM if pequeno else CAP_BOTTOM, housing)
        return out


__all__ = ["TrafficLight"]
