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

SOUND_KEY = "B"  # alterna o bip: a descrição vira MUTED quando está desligado
NOTIFY_KEY = "N"  # alterna a notificação do sistema: vira MUTED quando desligada
SORT_KEY = "S"  # ordena por atenção: apagada enquanto a ordem é a de descoberta

# (tecla, descrição, prioridade). A ORDEM da lista é a de leitura na barra; a
# prioridade só decide quem sai primeiro quando não cabe — maior fica por último.
KEYS = [
    ("↑↓", "NAV", 12),
    ("ENTER", "OPEN", 11),
    ("⇧A", "GO", 10),
    ("TAB", "PANEL", 6),
    ("T", "THEMES", 5),
    ("V", "VIEW", 9),
    ("S", "SORT", 4),
    ("R", "REFRESH", 3),
    ("B", "BEEP", 2),
    ("N", "NOTIF", 1),
    ("?", "HELP", 8),
    ("Q", "QUIT", 7),
]


class KeyBar(Widget):
    DEFAULT_CSS = "KeyBar { height: 1; }"

    def on_mount(self) -> None:
        self.watch(self.app, "sound_on", lambda _: self.refresh())
        self.watch(self.app, "notify_on", lambda _: self.refresh())

    @property
    def sound_on(self) -> bool:
        return getattr(self.app, "sound_on", True)

    @property
    def notify_on(self) -> bool:
        return getattr(self.app, "notify_on", True)

    @property
    def sort_on(self) -> bool:
        return getattr(self.app, "sort_on", False)

    def _desligado(self, key: str) -> bool:
        """Interruptores apagam a própria tecla quando estão desligados."""
        return (
            (key == SOUND_KEY and not self.sound_on)
            or (key == NOTIFY_KEY and not self.notify_on)
            or (key == SORT_KEY and not self.sort_on)
        )

    def _keys(self) -> list[tuple[str, str, int]]:
        """KEYS com os dois interruptores descrevendo o estado atual."""
        rotulos = {
            SOUND_KEY: "BEEP" if self.sound_on else "MUTED",
            NOTIFY_KEY: "NOTIF" if self.notify_on else "MUTED",
        }
        return [
            (key, rotulos.get(key, desc), priority) for key, desc, priority in KEYS
        ]

    def _build(self, keys, with_desc: bool) -> Text:
        out = Text(no_wrap=True, overflow="ellipsis")
        for i, (key, desc, _) in enumerate(keys):
            if i:
                out.append(" │ " if with_desc else "  ", Style(color=colors().line_hi))
            off = self._desligado(key)
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
