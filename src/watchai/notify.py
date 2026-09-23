"""Notificação do sistema — o aviso que aparece mesmo com o WatchAI escondido.

O bip resolve "alguma coisa mudou"; a notificação resolve **o quê e onde**, com
a janela minimizada ou noutra área de trabalho. Os dois andam juntos e o mesmo
`B` liga e desliga.

Um mecanismo por sistema, descoberto uma vez e degradando em silêncio:

* Linux    — `notify-send` (libnotify, presente em qualquer desktop atual)
* macOS    — `osascript -e 'display notification …'`
* Windows  — toast por PowerShell (WinRT); **não verificado em máquina real**.

Nada aqui pode travar a UI nem derrubar o app: comando que não existe vira
`available = False`, e notificador que falha é **desligado na primeira falha**,
com o motivo guardado em `erro`. Antes ele falhava em silêncio e continuava
sendo chamado — o pior dos dois mundos: nenhum aviso na tela e um processo
inútil a cada mudança de estado.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import sys

APP_NAME = "WatchAI"

# Urgência do notify-send por estado (o que decide se a notificação fica na
# tela até você ver).
URGENCIA = {"error": "critical", "input": "critical", "ready": "normal"}

# O `pwsh` (PowerShell 7) **não projeta WinRT**: o mesmo script que funciona no
# Windows PowerShell 5.1 falha ali ao carregar o tipo do toast. Por isso a ordem
# não é "o que existir na máquina" — é o 5.1 primeiro.
POWERSHELL = ("powershell", "pwsh")

# Teto de espera pelo notificador. Passou disso, ele que fique para trás.
TIMEOUT = 5.0

# O identificador do app (AUMID) precisa estar **registrado** no Windows para a
# notificação aparecer: com um nome inventado, o toast é criado, não dá erro e
# não aparece na tela — a falha mais difícil de diagnosticar que existe. O AUMID
# do próprio Windows PowerShell já é registrado em toda instalação, e é o que
# ferramentas de linha de comando usam para não precisar instalar um atalho.
TOAST_AUMID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

# Toast do Windows sem instalar módulo nenhum: WinRT puro.
TOAST_PS = """
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime] | Out-Null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
    [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $xml.GetElementsByTagName('text')
$texts.Item(0).AppendChild($xml.CreateTextNode($env:WATCHAI_TITLE)) | Out-Null
$texts.Item(1).AppendChild($xml.CreateTextNode($env:WATCHAI_BODY)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:WATCHAI_AUMID).Show($toast)
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
        # Por que parou de funcionar, quando parou. Vazio enquanto está tudo bem.
        self.erro = ""

    @property
    def available(self) -> bool:
        return bool(self.mechanism)

    def _desligar(self, motivo: str) -> None:
        """Um notificador que falhou uma vez falha sempre — o mecanismo não
        existe, a permissão não está lá, o tipo não carrega. Insistir custa um
        processo a cada mudança de estado e não põe nada na tela."""
        self.mechanism = None
        self.erro = " ".join(motivo.split())[:200] or "falhou sem dizer por quê"

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
        env = {"WATCHAI_TITLE": title, "WATCHAI_BODY": body, "WATCHAI_AUMID": TOAST_AUMID}
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
                # O stderr é lido, não descartado: é a única pista de por que o
                # toast do Windows não apareceu.
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as erro:
            self._desligar(f"{command[0]}: {erro}")
            return
        try:
            _, saida = await asyncio.wait_for(process.communicate(), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            # Notificador travado não pode segurar o app — e matar um processo
            # que já morreu sozinho no meio do caminho também não pode quebrar.
            with contextlib.suppress(ProcessLookupError, OSError):
                process.kill()
            self._desligar(f"{command[0]} não respondeu em {TIMEOUT:.0f}s")
            return
        if process.returncode:
            self._desligar((saida or b"").decode("utf-8", "replace") or f"código {process.returncode}")


__all__ = ["APP_NAME", "Notifier", "TIMEOUT", "TOAST_AUMID", "find_notifier"]
