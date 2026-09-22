"""THEMES — seletor de tema com preview ao vivo.

Mover a seleção **aplica** o tema na hora: o dashboard inteiro atrás do modal
troca de cor, então dá para ver como fica antes de decidir. `ENTER` confirma e
grava; `ESC` desfaz e volta para o tema em que você estava.

Cada linha traz uma amostra dos estados desenhada com as cores **daquela**
paleta, para comparar sem precisar visitar uma por uma.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static

from ..models import SUMMARY_ORDER
from ..theme import PALETTES, Palette, colors

LABEL_W = 12


class ThemeScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Apply", show=False),
        Binding("up,k", "move(-1)", "Up", show=False),
        Binding("down,j", "move(1)", "Down", show=False),
        Binding("t", "cancel", "Close", show=False),
    ]

    index: reactive[int] = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self.original: str = ""

    def compose(self):
        with Vertical(id="themes"):
            yield Static("", id="themes-body")

    def on_mount(self) -> None:
        self.query_one("#themes").border_title = "THEMES"
        self.original = self.app.palette_key
        self.index = next(
            (i for i, p in enumerate(PALETTES) if p.key == self.original), 0
        )
        self._render_body()

    # -- conteúdo ---------------------------------------------------------------
    def _sample(self, palette: Palette) -> Text:
        """Os símbolos dos estados nas cores desta paleta."""
        out = Text(no_wrap=True)
        for status in SUMMARY_ORDER:
            out.append(status.symbol + " ", Style(color=getattr(palette, status.slot)))
        return out

    def _body(self) -> Text:
        c = colors()
        out = Text(no_wrap=True, overflow="ellipsis")
        for i, palette in enumerate(PALETTES):
            selected = i == self.index
            out.append(
                "▶ " if selected else "  ",
                Style(color=c.cyan, bold=True),
            )
            out.append(
                palette.label.ljust(LABEL_W),
                Style(color=c.cyan if selected else c.text, bold=selected),
            )
            out.append_text(self._sample(palette))
            if palette.key == self.original:
                out.append(" •", Style(color=c.muted))
            out.append("\n")
        out.append("\n")
        # 37 colunas — cabe nas 38 úteis do modal (46 menos borda e padding).
        out.append("↑↓", Style(color=c.cyan, bold=True))
        out.append(" preview   ", Style(color=c.muted))
        out.append("ENTER", Style(color=c.cyan, bold=True))
        out.append(" apply   ", Style(color=c.muted))
        out.append("ESC", Style(color=c.cyan, bold=True))
        out.append(" cancel", Style(color=c.muted))
        return out

    def _render_body(self) -> None:
        self.query_one("#themes-body", Static).update(self._body())

    # -- ações ------------------------------------------------------------------
    def watch_index(self, index: int) -> None:
        if not self.is_mounted:
            return
        # Aplicar no movimento é o preview: tudo atrás do modal troca de cor.
        self.app.apply_palette(PALETTES[index].key)
        self._render_body()

    def action_move(self, delta: int) -> None:
        self.index = (self.index + delta) % len(PALETTES)

    def action_confirm(self) -> None:
        key = PALETTES[self.index].key
        self.app.apply_palette(key, remember=True)
        self.dismiss(key)

    def action_cancel(self) -> None:
        self.app.apply_palette(self.original)
        self.dismiss(None)
