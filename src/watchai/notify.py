"""Notificação do sistema — o aviso que aparece mesmo com o WatchAI escondido.

O bip resolve "alguma coisa mudou"; a notificação resolve **o quê e onde**, com
a janela minimizada ou noutra área de trabalho. Os dois andam juntos e o mesmo
`B` liga e desliga.

Um mecanismo por sistema, descoberto uma vez e degradando em silêncio:

* Linux    — `notify-send` (libnotify, presente em qualquer desktop atual)
* macOS    — `osascript -e 'display notification …'`
* Windows  — toast por PowerShell (WinRT); **não verificado em máquina real**,
  por isso a falha é silenciosa e o bip continua valendo.

Nada aqui pode travar a UI nem derrubar o app: comando que não existe vira
`available = False`, e comando que falha some sem avisar.
"""

from __future__ import annotations

import asyncio
import shutil
import sys

APP_NAME = "WatchAI"

# Urgência do notify-send por estado (o que decide se a notificação fica na
# tela até você ver).
URGENCIA = {"error": "critical", "input": "critical", "ready": "normal"}

POWERSHELL = ("powershell", "pwsh")

# Toast do Windows sem instalar módulo nenhum: WinRT puro.
TOAST_PS = """
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
    [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $xml.GetElementsByTagName('text')
$texts.Item(0).AppendChild($xml.CreateTextNode($env:WATCHAI_TITLE)) | Out-Null
$texts.Item(1).AppendChild($xml.CreateTextNode($env:WATCHAI_BODY)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('WatchAI').Show($toast)
"""


def find_notifier() -> str | None:
    """Qual mecanismo esta máquina tem: 'notify-send', 'osascript', 'toast'."""
    if sys.platform == "darwin":
        return "osascript" if shutil.which("osascript") else None
    if sys.platform == "win32":
        return "toast" if any(shutil.which(p) for p in POWERSHELL) else None
    return "notify-send" if shutil.which("notify-send") else None


def _escape_applescript(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"')


class Notifier:
    """Manda a notificação. `available` diz se a máquina tem como."""

    def __init__(self, mechanism: str | None = ...) -> None:  # type: ignore[assignment]
        self.mechanism = find_notifier() if mechanism is ... else mechanism

    @property
    def available(self) -> bool:
        return bool(self.mechanism)

    def _command(self, title: str, body: str, kind: str) -> tuple[list[str], dict[str, str]]:
        env: dict[str, str] = {}
        if self.mechanism == "notify-send":
            urgencia = URGENCIA.get(kind, "normal")
            return (
                [
                    "notify-send",
                    "--app-name",
                    APP_NAME,
                    "--urgency",
                    urgencia,
                    "--icon",
                    "utilities-terminal",
                    title,
                    body,
                ],
                env,
            )
        if self.mechanism == "osascript":
            script = (
                f'display notification "{_escape_applescript(body)}" '
                f'with title "{APP_NAME}" subtitle "{_escape_applescript(title)}"'
            )
            return (["osascript", "-e", script], env)
        exe = next((shutil.which(p) for p in POWERSHELL if shutil.which(p)), None)
        if not exe:
            return ([], env)
        # O texto vai por variável de ambiente: assim aspas e acentos no nome do
        # projeto não viram injeção de script.
        env = {"WATCHAI_TITLE": title, "WATCHAI_BODY": body}
        return ([exe, "-NoProfile", "-NonInteractive", "-Command", TOAST_PS], env)

    async def send(self, title: str, body: str, kind: str = "ready") -> None:
        if not self.mechanism:
            return
        command, extra = self._command(title, body, kind)
        if not command:
            return
        env = None
        if extra:
            import os

            env = {**os.environ, **extra}
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            self.mechanism = None  # sumiu: para de tentar
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()  # notificador travado não pode segurar o app


__all__ = ["APP_NAME", "Notifier", "find_notifier"]
