"""Bip de atenção — o aviso de que uma sessão precisa de você.

Toca pelo **servidor de som** do sistema, não pelo bell do terminal (`\\a`).
Essa é a diferença que importa: o bell vira flash visual em vários emuladores,
costuma estar desligado por padrão e não ajuda com a aba em segundo plano. Um
stream de áudio normal toca independente de foco — que é exatamente o caso de
uso: você está em outra janela e quer ser avisado.

O bell fica como último recurso, para quando não há player nenhum.

**Um timbre por estado.** READY, INPUT e ERROR avisam coisas diferentes
("terminou", "parou esperando você", "quebrou") e não adianta avisar os três
com o mesmo som: você teria que olhar para saber qual foi. Cada um pega um som
do tema do sistema — nada é embutido no pacote.

A descoberta acontece uma vez, na criação; depois cada bip é só um spawn
(~0,6 ms) cujo processo é aguardado dentro do event loop, sem zumbis.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

READY, INPUT, ERROR = "ready", "input", "error"
KINDS = (READY, INPUT, ERROR)

# (executável, argumentos que vêm antes do arquivo). Ordem = preferência.
PLAYERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pw-play", ()),  # PipeWire (padrão no Ubuntu atual)
    ("paplay", ()),  # PulseAudio
    ("afplay", ()),  # macOS
    ("ffplay", ("-nodisp", "-autoexit", "-loglevel", "quiet")),
)

# Sons dos temas do sistema, do preferido para o alternativo. Linux e macOS.
SOUNDS: dict[str, tuple[str, ...]] = {
    READY: (
        "/usr/share/sounds/Yaru/stereo/bell.oga",
        "/usr/share/sounds/freedesktop/stereo/bell.oga",
        "/usr/share/sounds/gnome/default/alerts/glass.ogg",
        "/System/Library/Sounds/Glass.aiff",
    ),
    INPUT: (
        "/usr/share/sounds/Yaru/stereo/message-new-instant.oga",
        "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga",
        "/usr/share/sounds/Yaru/stereo/message.oga",
        "/usr/share/sounds/freedesktop/stereo/message.oga",
        "/System/Library/Sounds/Ping.aiff",
    ),
    ERROR: (
        "/usr/share/sounds/Yaru/stereo/dialog-warning.oga",
        "/usr/share/sounds/freedesktop/stereo/dialog-error.oga",
        "/usr/share/sounds/gnome/default/alerts/sonar.ogg",
        "/System/Library/Sounds/Basso.aiff",
    ),
}

# Sem arquivo de som: libcanberra toca o evento do tema, seja ele qual for.
CANBERRA_EVENT = {READY: "bell", INPUT: "message-new-instant", ERROR: "dialog-warning"}

# Windows não tem arquivo canônico: usa os sons de sistema do .NET.
WINDOWS_SOUND = {READY: "Asterisk", INPUT: "Question", ERROR: "Hand"}

# E o plano B, quando o `System.Media` não está lá: o beep do console, que
# existe desde sempre e não depende de esquema de som nenhum. Uma frequência
# por estado mantém o que importa — três avisos distinguíveis sem olhar.
WINDOWS_BEEP = {READY: (880, 180), INPUT: (620, 220), ERROR: (320, 320)}

# O Windows PowerShell 5.1 vem com o `System.Media`; o `pwsh` (PowerShell 7)
# não — ali a classe mora num pacote que nem sempre está instalado. Por isso o
# 5.1 vem primeiro, e por isso o script tem `try`/`catch` em vez de confiar.
POWERSHELL = ("powershell", "pwsh")


def _windows_command(kind: str) -> list[str] | None:
    exe = next((shutil.which(p) for p in POWERSHELL if shutil.which(p)), None)
    if not exe:
        return None
    som = WINDOWS_SOUND.get(kind, WINDOWS_SOUND[READY])
    hz, ms = WINDOWS_BEEP.get(kind, WINDOWS_BEEP[READY])
    return [
        exe,
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        f"try {{ [System.Media.SystemSounds]::{som}.Play(); Start-Sleep -Milliseconds 500 }} "
        f"catch {{ [Console]::Beep({hz}, {ms}) }}",
    ]


def find_player(kind: str = READY) -> list[str] | None:
    """Comando pronto para tocar o aviso deste estado, ou None se a máquina
    não tiver como."""
    if sys.platform == "win32":
        return _windows_command(kind)

    sound = next((s for s in SOUNDS.get(kind, ()) if Path(s).is_file()), None)
    if sound:
        for exe, args in PLAYERS:
            found = shutil.which(exe)
            if found:
                return [found, *args, sound]
    canberra = shutil.which("canberra-gtk-play")
    if canberra:
        return [canberra, "-i", CANBERRA_EVENT.get(kind, "bell")]
    return None


class Alert:
    """Toca o aviso. `available` diz se há player — sem ele, quem chama cai no
    bell do terminal.

    `command` força o mesmo comando para todos os estados (é o que a suíte usa
    para não tocar nada de verdade).
    """

    def __init__(self, command: list[str] | None = None) -> None:
        if command is not None:
            self.commands: dict[str, list[str] | None] = {k: command for k in KINDS}
        else:
            self.commands = {k: find_player(k) for k in KINDS}

    @property
    def available(self) -> bool:
        return any(self.commands.values())

    @property
    def command(self) -> list[str] | None:
        """O comando do aviso padrão (READY)."""
        return self.commands.get(READY)

    async def play(self, kind: str = READY) -> None:
        command = self.commands.get(kind) or self.commands.get(READY)
        if not command:
            return
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            # Player sumiu no meio do caminho: desiste sem derrubar a UI.
            self.commands[kind] = None
            return
        await process.wait()  # aguardar aqui é o que evita processo zumbi


__all__ = [
    "Alert",
    "ERROR",
    "INPUT",
    "KINDS",
    "PLAYERS",
    "READY",
    "SOUNDS",
    "WINDOWS_BEEP",
    "find_player",
]
