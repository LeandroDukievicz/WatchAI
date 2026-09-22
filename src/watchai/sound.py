"""Bip de atenção — o aviso de que uma sessão ficou READY.

Toca pelo **servidor de som** (PipeWire/PulseAudio), não pelo bell do terminal
(`\\a`). Essa é a diferença que importa: o bell vira flash visual em vários
emuladores, costuma estar desligado por padrão e não ajuda com a aba em segundo
plano. Um stream de áudio normal toca independente de foco — que é exatamente o
caso de uso: você está em outra janela e quer ser avisado.

O bell do terminal fica como último recurso, para quando não há player nenhum.

A descoberta do player acontece uma vez, na criação; depois cada bip é só um
spawn (~0,6 ms) cujo processo é aguardado dentro do event loop, sem zumbis.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

# (executável, argumentos que vêm antes do arquivo). Ordem = preferência.
PLAYERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pw-play", ()),  # PipeWire (padrão no Ubuntu atual)
    ("paplay", ()),  # PulseAudio
    ("ffplay", ("-nodisp", "-autoexit", "-loglevel", "quiet")),
)

# Bips curtos dos temas de som do sistema, do mais seco para o mais longo.
SOUNDS: tuple[str, ...] = (
    "/usr/share/sounds/Yaru/stereo/bell.oga",
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
    "/usr/share/sounds/gnome/default/alerts/glass.ogg",
)

# Sem arquivo de som: libcanberra toca o evento do tema, seja ele qual for.
CANBERRA = ("canberra-gtk-play", "-i", "bell")


def find_player() -> list[str] | None:
    """Comando pronto para tocar o bip, ou None se a máquina não tiver como."""
    sound = next((s for s in SOUNDS if Path(s).is_file()), None)
    if sound:
        for exe, args in PLAYERS:
            found = shutil.which(exe)
            if found:
                return [found, *args, sound]
    canberra = shutil.which(CANBERRA[0])
    if canberra:
        return [canberra, *CANBERRA[1:]]
    return None


class Alert:
    """Toca o bip. `available` diz se há player — sem ele, quem chama cai no
    bell do terminal."""

    def __init__(self, command: list[str] | None = None) -> None:
        self.command = command if command is not None else find_player()

    @property
    def available(self) -> bool:
        return bool(self.command)

    async def play(self) -> None:
        if not self.command:
            return
        try:
            process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            # Player sumiu no meio do caminho: desiste sem derrubar a UI.
            self.command = None
            return
        await process.wait()  # aguardar aqui é o que evita processo zumbi


__all__ = ["Alert", "find_player", "PLAYERS", "SOUNDS"]
