"""Barra de atalhos (rodapé). Tecla em cyan, descrição em cinza.

    ↑↓ NAV │ ENTER OPEN │ TAB PANEL │ V VIEW │ R REFRESH │ ? HELP │ Q QUIT

Em larguras pequenas descarta os atalhos menos importantes (prioridade menor
primeiro) e, se ainda não couber, mostra só as teclas.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.widget import Widget

from ..theme import colors

SOUND_KEY = "B"  # alterna o bip: a descrição vira MUDO quando está desligado

# (tecla, descrição, prioridade — maior = descarta por último)
KEYS = [
    ("↑↓", "NAV", 9),
    ("ENTER", "OPEN", 8),
    ("TAB", "PANEL", 4),
    ("T", "THEMES", 3),
    ("V", "VIEW", 7),
    ("R", "REFRESH", 2),
    ("B", "BIP", 1),
    ("?", "HELP", 6),
    ("Q", "QUIT", 5),
]


class KeyBar(Widget):
    DEFAULT_CSS = "KeyBar { height: 1; }"

    def on_mount(self) -> None:
        self.watch(self.app, "sound_on", lambda _: self.refresh())

    @property
    def sound_on(self) -> bool:
        return getattr(self.app, "sound_on", True)

    def _keys(self) -> list[tuple[str, str, int]]:
        """KEYS com a tecla do bip descrevendo o estado atual."""
        label = "BIP" if self.sound_on else "MUDO"
        return [
            (key, label if key == SOUND_KEY else desc, priority)
            for key, desc, priority in KEYS
        ]

    def _build(self, keys, with_desc: bool) -> Text:
        muted = not self.sound_on
        out = Text(no_wrap=True, overflow="ellipsis")
        for i, (key, desc, _) in enumerate(keys):
            if i:
                out.append(" │ " if with_desc else "  ", Style(color=colors().line_hi))
            off = muted and key == SOUND_KEY
            out.append(key, Style(color=colors().ghost if off else colors().cyan, bold=not off))
            if with_desc:
                out.append(f" {desc}", Style(color=colors().ghost if off else colors().muted))
        return out

    def render(self) -> Text:
        width = self.size.width
        keys = self._keys()
        while keys:
            text = self._build(keys, True)
            if text.cell_len <= width:
                return text
            keys.remove(min(keys, key=lambda k: k[2]))
        return self._build(self._keys(), False)
