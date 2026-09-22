"""StatusLight — o indicador de estado (o elemento visual mais importante).

TODA representação de estado no app passa por aqui:
  * `render_status()` devolve o `Text` (símbolo + label) — usado também em
    lugares que não são widgets (Event Stream, cabeçalho);
  * `StatusLight` é o widget reutilizável (cards, lista, detalhes).

Cada estado tem cor + símbolo + label, então dá para distinguir sem depender
só de cor (daltonismo): ● ready · ◐ working · ◇ waiting · ◆ input · ▲ error ·
○ offline · ◌ starting.

Animações (todas discretas, guiadas pelo `tick` do app, 0.5 s):
  WORKING   giro lento ◐ ◓ ◑ ◒  (cyan, sem negrito → não chama atenção)
  READY     pulso lento do símbolo (~4.5 s por ciclo)
  INPUT     mesmo pulso lento, em magenta
  STARTING  ◌ ○ alternando a cada 1 s
  ERROR     estático
  OFFLINE   estático e apagado
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from ..models import Status
from ..theme import colors, fade

SPINNER = "◐◓◑◒"
# Níveis de brilho de um ciclo de pulso lento (1.0 = cor cheia).
PULSE = (1.0, 1.0, 0.92, 0.78, 0.64, 0.56, 0.64, 0.78, 0.92)

# Estados cujo label é destacado (negrito): são os que pedem o usuário.
_BOLD = {Status.READY, Status.INPUT, Status.ERROR}


def status_symbol(status: Status, tick: int = 0) -> str:
    if status is Status.WORKING:
        return SPINNER[tick % len(SPINNER)]
    if status is Status.STARTING:
        return "◌○"[(tick // 2) % 2]
    return status.symbol


def status_color(status: Status, tick: int = 0) -> str:
    """Cor do símbolo neste tick (aplica o pulso em READY/INPUT)."""
    if status in (Status.READY, Status.INPUT):
        return fade(status.color, PULSE[tick % len(PULSE)])
    return status.color


def render_status(status: Status, tick: int = 0, *, label: bool = True) -> Text:
    """'● READY' como Rich Text. Fonte única de estilo dos estados."""
    text = Text(no_wrap=True, overflow="ellipsis")
    text.append(
        status_symbol(status, tick),
        Style(color=status_color(status, tick), bold=status in _BOLD),
    )
    if label:
        text.append(" ")
        text.append(
            status.label,
            Style(
                color=colors().gray if status is Status.OFFLINE else status.color,
                bold=status in _BOLD,
                dim=status is Status.OFFLINE,
            ),
        )
    return text


class StatusLight(Widget):
    """Indicador reutilizável: `● READY`, com sufixo opcional alinhado à direita
    (ex.: `for 01:42`)."""

    DEFAULT_CSS = """
    StatusLight { height: 1; width: auto; }
    """

    status: reactive[Status] = reactive(Status.OFFLINE)
    tick: reactive[int] = reactive(0)

    def __init__(
        self,
        status: Status = Status.OFFLINE,
        *,
        show_label: bool = True,
        suffix: str = "",
        suffix_style: str = "",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.show_label = show_label
        self._suffix = suffix
        self._suffix_style = suffix_style
        self.set_reactive(StatusLight.status, status)

    def on_mount(self) -> None:
        self.watch(self.app, "tick", self._on_tick)

    def _on_tick(self, value: int) -> None:
        # Só repinta quando há o que animar (ou sufixo mudando).
        if self.status in (Status.WORKING, Status.READY, Status.INPUT, Status.STARTING):
            self.tick = value

    def set_suffix(self, suffix: str, style: str = "") -> None:
        if (suffix, style) != (self._suffix, self._suffix_style):
            self._suffix, self._suffix_style = suffix, style
            self.refresh()

    def content_width(self) -> int:
        return len(self.status.label) + 2 if self.show_label else 1

    def render(self) -> Text:
        text = render_status(self.status, self.tick, label=self.show_label)
        width = self.size.width
        if self._suffix and width:
            gap = width - text.cell_len - len(self._suffix)
            if gap >= 2:
                text.append(" " * gap)
                text.append(self._suffix, Style.parse(self._suffix_style or colors().muted))
        return text

    def get_content_width(self, container, viewport) -> int:  # type: ignore[override]
        return self.content_width()


__all__ = [
    "StatusLight",
    "render_status",
    "status_color",
    "status_symbol",
]
