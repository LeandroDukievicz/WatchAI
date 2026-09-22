"""Levar você até a janela onde a sessão está rodando.

O card diz que o CLAUDE terminou; `G` põe na frente a janela do terminal em que
ele roda. É o fim natural do fluxo: ver, decidir, voltar.

Cada sistema tem um jeito, e não é por capricho:

* **macOS** — `System Events` ativa um processo pelo PID.
* **Windows** — `AppActivate` do WScript.Shell, também pelo PID.
* **Linux/X11** — `wmctrl` ou `xdotool` casam janela e PID.
* **Linux/Wayland** — o compositor **proíbe** um app levantar a janela de
  outro (é proteção contra roubo de foco). Resta pedir ao próprio terminal, via
  D-Bus (`org.freedesktop.Application.Activate`), quando ele for um app GTK que
  expõe essa interface.

E quando nada disso existe, sobra o recurso mais antigo do Unix: **tocar o sino
na tty da sessão**. O terminal marca a janela como "precisa de atenção" — na
dock do GNOME ela pisca. Não é foco, mas é evidência, e funciona em qualquer
lugar onde a tty seja sua.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys

# Nome do processo do emulador -> app id no D-Bus (apps GTK/Qt que expõem
# org.freedesktop.Application).
APPS_DBUS = {
    "gnome-terminal-server": "org.gnome.Terminal",
    "ptyxis": "org.gnome.Ptyxis",
    "ptyxis-agent": "org.gnome.Ptyxis",
    "kgx": "org.gnome.Console",
    "konsole": "org.kde.konsole",
    "tilix": "com.gexperts.Tilix",
    "terminator": "net.launchpad.terminator.Terminator",
    "alacritty": "org.alacritty.Alacritty",
    "wezterm-gui": "org.wezfurlong.wezterm",
}

# Nomes que identificam um emulador de terminal na árvore de processos.
EMULADORES = frozenset(
    {
        *APPS_DBUS,
        "xterm",
        "urxvt",
        "rxvt",
        "st",
        "kitty",
        "foot",
        "contour",
        "xfce4-terminal",
        "mate-terminal",
        "lxterminal",
        "qterminal",
        "terminology",
        "hyper",
        "warp",
        "windowsterminal",
        "wt",
        "conhost",
        "openconsole",
        "terminal",
        "iterm2",
    }
)

OSASCRIPT = (
    'tell application "System Events" to set frontmost of '
    "(first process whose unix id is {pid}) to true"
)
POWERSHELL_ACTIVATE = "(New-Object -ComObject WScript.Shell).AppActivate({pid})"


def detect() -> str | None:
    """O mecanismo desta máquina: 'osascript', 'powershell', 'wmctrl',
    'xdotool', 'gdbus' — ou None, e aí resta o sino."""
    if sys.platform == "darwin":
        return "osascript" if shutil.which("osascript") else None
    if sys.platform == "win32":
        return "powershell" if shutil.which("powershell") or shutil.which("pwsh") else None
    if shutil.which("wmctrl"):
        return "wmctrl"
    if shutil.which("xdotool"):
        return "xdotool"
    if shutil.which("gdbus"):
        return "gdbus"
    return None


async def _rodar(comando: list[str], timeout: float = 5.0) -> tuple[int, str]:
    """Roda e devolve (código, saída). Nunca levanta."""
    try:
        processo = await asyncio.create_subprocess_exec(
            *comando,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        return 127, ""
    try:
        saida, _ = await asyncio.wait_for(processo.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        processo.kill()
        return 124, ""
    return processo.returncode or 0, (saida or b"").decode("utf-8", "replace")


def ring(tty: str | None) -> bool:
    """Toca o sino na tty da sessão: a janela dela pede atenção na barra.

    É o plano B universal — e o único caminho no Wayland quando o terminal não
    fala D-Bus.
    """
    if not tty or not tty.startswith("/dev/"):
        return False
    try:
        fd = os.open(tty, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        os.write(fd, b"\a")
        return True
    finally:
        os.close(fd)


class Focuser:
    """Põe na frente a janela de uma sessão. `available` diz se há mecanismo
    além do sino."""

    def __init__(self, method: str | None = ...) -> None:  # type: ignore[assignment]
        self.method = detect() if method is ... else method

    @property
    def available(self) -> bool:
        return bool(self.method)

    async def _janela_wmctrl(self, pid: int, title: str | None) -> str | None:
        """O id da janela daquele processo.

        Um servidor de terminal (gnome-terminal, konsole) hospeda **todas** as
        janelas com o mesmo PID: quando há mais de uma, o título da sessão é o
        que desempata.
        """
        código, saida = await _rodar(["wmctrl", "-l", "-p"])
        if código != 0:
            return None
        candidatas: list[tuple[str, str]] = []
        for linha in saida.splitlines():
            partes = linha.split(None, 4)  # id, área, pid, host, título
            if len(partes) < 5:
                continue
            if partes[2] == str(pid):
                candidatas.append((partes[0], partes[4]))
        if not candidatas:
            return None
        if title:
            alvo = title.lower()
            for janela, titulo in candidatas:
                if alvo in titulo.lower():
                    return janela
        return candidatas[0][0]

    async def focus(
        self,
        *,
        pid: int | None = None,
        app: str | None = None,
        tty: str | None = None,
        title: str | None = None,
    ) -> str:
        """Tenta focar e devolve, em uma linha, o que conseguiu fazer."""
        if pid and self.method == "osascript":
            código, _ = await _rodar(["osascript", "-e", OSASCRIPT.format(pid=pid)])
            if código == 0:
                return "janela em evidência"
        elif pid and self.method == "powershell":
            exe = shutil.which("powershell") or shutil.which("pwsh")
            if exe:
                código, _ = await _rodar(
                    [exe, "-NoProfile", "-NonInteractive", "-Command",
                     POWERSHELL_ACTIVATE.format(pid=pid)]
                )
                if código == 0:
                    return "janela em evidência"
        elif pid and self.method == "wmctrl":
            janela = await self._janela_wmctrl(pid, title)
            if janela:
                código, _ = await _rodar(["wmctrl", "-i", "-a", janela])
                if código == 0:
                    return "janela em evidência"
        elif pid and self.method == "xdotool":
            código, saida = await _rodar(["xdotool", "search", "--pid", str(pid)])
            ids = [linha for linha in saida.split() if linha.strip()]
            if código == 0 and ids:
                código, _ = await _rodar(["xdotool", "windowactivate", ids[-1]])
                if código == 0:
                    return "janela em evidência"
        elif self.method == "gdbus" and app:
            destino = APPS_DBUS.get(app)
            if destino:
                caminho = "/" + destino.replace(".", "/")
                código, _ = await _rodar(
                    ["gdbus", "call", "--session", "--dest", destino,
                     "--object-path", caminho,
                     "--method", "org.freedesktop.Application.Activate", "{}"]
                )
                if código == 0:
                    # O Activate levanta a janela, mas quem escolhe a aba é o
                    # terminal. O sino na tty marca a aba certa — as duas coisas
                    # juntas chegam onde o Wayland sozinho não deixa.
                    if ring(tty):
                        return "janela à frente e aba sinalizada"
                    return "terminal chamado para a frente"

        if ring(tty):
            return f"sino tocado em {tty.replace('/dev/', '')} — a janela pede atenção"
        return "não consegui chegar nessa janela"


__all__ = ["APPS_DBUS", "EMULADORES", "Focuser", "detect", "ring"]
