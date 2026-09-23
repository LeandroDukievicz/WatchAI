"""Levar você até a janela onde a sessão está rodando.

O card diz que o CLAUDE terminou; `G` põe na frente a janela do terminal em que
ele roda. É o fim natural do fluxo: ver, decidir, voltar.

Cada sistema tem um jeito, e não é por capricho:

* **macOS** — `System Events`. `set frontmost` sozinho levanta o **app**, não a
  janela, e não tira nada da Dock: o script escolhe a janela, zera o
  `AXMinimized`, levanta com `AXRaise` e confere se o app ficou na frente.
* **Windows** — `AppActivate` do WScript.Shell, com `SW_RESTORE` antes para a
  janela minimizada e `GetForegroundWindow` depois para conferir. O código de
  saída do PowerShell não serve de resposta: ele é zero mesmo quando o
  `AppActivate` devolve `False`.
* **Linux/X11** — `wmctrl` ou `xdotool` casam janela e PID.
* **Linux/Wayland** — o compositor **proíbe** um app levantar a janela de
  outro (é proteção contra roubo de foco), e o GNOME 50 já nem tem sessão X11
  para escapar por ela. O único caminho preciso é a extensão **[Window Calls]**,
  que expõe `List`, `Unminimize` e `Activate` no D-Bus.

  [Window Calls]: https://extensions.gnome.org/extension/4724/window-calls/

Sem a extensão sobra pedir ao terminal que se levante
(`org.freedesktop.Application.Activate`), e aí vem a armadilha que justifica
metade deste arquivo: **no Wayland esse pedido volta com sucesso e é ignorado**.
Quem chama recebe código 0, a janela não se move, e o app anuncia uma coisa que
não aconteceu. Por isso aqui só é sucesso o que dá para conferir: com a extensão
instalada, relendo o `focus` da janela depois do `Activate`; sem ela, nada no
Wayland é sucesso.

O que resta então é o recurso mais antigo do Unix: **tocar o sino na tty da
sessão**. O terminal marca a janela como "precisa de atenção" — na dock do GNOME
ela pisca. Não é foco, e numa janela minimizada não restaura nada, mas é
evidência, e funciona em qualquer lugar onde a tty seja sua.

Um detalhe que atravessa tudo: um servidor de terminal (gnome-terminal, konsole)
hospeda **todas** as janelas num processo só, e o PID não identifica janela ali.
O título também não: numa máquina real ele é de quem está rodando na aba — o
agente escreve o que está fazendo, um player escreve a música, o shell escreve
`usuário@host`. Quem identifica é a **tty**, e o jeito de perguntar é escrever
nela um título único (mesmo canal do sino), ver qual janela ficou com ele e
devolver o título de antes.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import sys
import time

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

# A extensão Window Calls, quando instalada, mora aqui.
WINDOW_CALLS = (
    "org.gnome.Shell",
    "/org/gnome/Shell/Extensions/Windows",
    "org.gnome.Shell.Extensions.Windows",
)

# macOS. `set frontmost` levanta o **app**, não a janela: com Terminal.app ou
# iTerm2 isso vai para a janela da frente, que pode não ser a da sessão — e
# janela minimizada na Dock não volta com ele. Por isso o script escolhe a
# janela pela marca (quando a tty respondeu ao OSC), tira do Dock pelo
# AXMinimized, levanta com AXRaise e só então confere se o app ficou na frente.
OSASCRIPT = """
tell application "System Events"
  set escolhidas to (every process whose unix id is __PID__)
  if escolhidas is {} then return "REFUSED"
  set alvo to item 1 of escolhidas
  set janelas to {}
  if "__MARCA__" is not "" then
    try
      set janelas to (every window of alvo whose name contains "__MARCA__")
    end try
  end if
  if janelas is {} then
    try
      set janelas to windows of alvo
    end try
  end if
  if janelas is {} then return "REFUSED"
  set janela to item 1 of janelas
  try
    set value of attribute "AXMinimized" of janela to false
  end try
  try
    perform action "AXRaise" of janela
  end try
  set frontmost of alvo to true
  delay 0.2
  if frontmost of alvo is true then return "RAISED"
  return "REFUSED"
end tell
"""

# Windows. O `AppActivate` devolve True/False, mas o PowerShell sai com código
# zero nos dois casos — ler só o código era o mesmo "sucesso falso" do Wayland.
# Aqui a janela minimizada é restaurada antes (SW_RESTORE = 9) e o resultado é
# conferido: quem está em primeiro plano é mesmo este processo? Cada pedaço
# arriscado tem try próprio, para que a falta de um não derrube o resto: sem
# como conferir, vale a palavra do AppActivate.
POWERSHELL_ACTIVATE = """
$alvo = __PID__
try {
  Add-Type -Name Janela -Namespace WatchAI -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h, int c);
[DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out uint p);
'@
  $proc = Get-Process -Id $alvo -ErrorAction SilentlyContinue
  if ($proc -and $proc.MainWindowHandle -ne [IntPtr]::Zero) {
    if ([WatchAI.Janela]::IsIconic($proc.MainWindowHandle)) {
      [WatchAI.Janela]::ShowWindowAsync($proc.MainWindowHandle, 9) | Out-Null
      Start-Sleep -Milliseconds 200
    }
  }
} catch { }
$ativou = $false
try { $ativou = (New-Object -ComObject WScript.Shell).AppActivate($alvo) } catch { }
Start-Sleep -Milliseconds 200
$confere = $null
try {
  $dono = [uint32]0
  $null = [WatchAI.Janela]::GetWindowThreadProcessId([WatchAI.Janela]::GetForegroundWindow(), [ref]$dono)
  $confere = ($dono -eq $alvo)
} catch { }
if ($confere -eq $true) { 'RAISED' }
elseif ($confere -eq $false) { 'REFUSED' }
elseif ($ativou) { 'RAISED' }
else { 'REFUSED' }
"""


def wayland() -> bool:
    """Estamos num compositor Wayland? É a diferença entre pedir foco e
    conseguir foco."""
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def gnome() -> bool:
    """A sessão é GNOME? A extensão Window Calls só existe ali — sugeri-la no
    KDE ou no sway seria mandar o usuário atrás de algo que não serve."""
    return "gnome" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower()


def detect() -> str | None:
    """O mecanismo desta máquina: 'osascript', 'powershell', 'wmctrl',
    'xdotool', 'gdbus' — ou None, e aí resta o sino."""
    if sys.platform == "darwin":
        return "osascript" if shutil.which("osascript") else None
    if sys.platform == "win32":
        return "powershell" if shutil.which("powershell") or shutil.which("pwsh") else None
    # No Wayland o wmctrl/xdotool até existem, mas não enxergam janela nativa:
    # usá-los seria falhar com cara de sucesso.
    if not wayland():
        if shutil.which("wmctrl"):
            return "wmctrl"
        if shutil.which("xdotool"):
            return "xdotool"
    if shutil.which("gdbus"):
        return "gdbus"
    return None


# Escapes que o g_variant_print emite ao imprimir texto.
_ESCAPES = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}


def _gvariant_string(saida: str) -> str | None:
    """O conteúdo de um `('...',)` devolvido pelo gdbus.

    O GVariant sai entre aspas simples — **menos** quando o próprio texto tem
    uma aspa simples, e aí o gdbus passa tudo para aspas duplas e escapa as
    internas. Como o texto aqui é a lista de janelas, basta **uma** janela com
    apóstrofo no título para o formato virar; ler só o primeiro caso fazia o
    WatchAI concluir que a extensão não estava instalada.
    """
    texto = saida.strip()
    if not (texto.startswith("(") and texto.endswith(")")):
        return None
    dentro = texto[1:-1].rstrip(",").strip()
    if len(dentro) < 2 or dentro[0] not in "'\"" or dentro[-1] != dentro[0]:
        return None
    corpo = dentro[1:-1]
    partes: list[str] = []
    i = 0
    while i < len(corpo):
        letra = corpo[i]
        if letra != "\\" or i + 1 >= len(corpo):
            partes.append(letra)
            i += 1
            continue
        seguinte = corpo[i + 1]
        if seguinte == "u" and i + 6 <= len(corpo):
            try:
                partes.append(chr(int(corpo[i + 2 : i + 6], 16)))
            except ValueError:
                partes.append(seguinte)
                i += 2
                continue
            i += 6
            continue
        partes.append(_ESCAPES.get(seguinte, seguinte))
        i += 2
    return "".join(partes)


def _alvos(title: str | None, directory: str | None) -> list[str]:
    """O que procurar no título da janela, do mais específico para o menos.

    O diretório vem primeiro porque o título de uma janela de terminal costuma
    ser o caminho (`~/Projetos/WatchAI`), enquanto o nome do projeto sozinho
    também casaria com uma janela aberta em outra pasta de nome parecido.
    """
    return [texto.lower() for texto in (directory, title) if texto]


def casar(pares: list, title: str | None = None, directory: str | None = None):
    """Entre janelas do mesmo processo, a que casa com a sessão — ou a primeira.

    `pares` é `[(id, texto)]`. É o desempate fraco, o que sobra quando a tty não
    identificou nada: serve quando o terminal titula a janela com o caminho, e
    erra quando quem titula é o programa de dentro.
    """
    if not pares:
        return None
    if len(pares) > 1:
        for alvo in _alvos(title, directory):
            for identificador, texto in pares:
                if alvo in (texto or "").lower():
                    return identificador
    return pares[0][0]


def _pares_de(janelas: list, pid: int) -> list:
    """As janelas daquele processo como `[(id, texto)]`, para o `casar`."""
    return [
        (
            j.get("id"),
            " ".join(str(j.get(c, "")) for c in ("title", "wm_class", "wm_class_instance")),
        )
        for j in janelas
        if isinstance(j, dict) and j.get("pid") == pid
    ]


def escolher(janelas: list, pid: int, title: str | None, directory: str | None = None) -> int | None:
    """Entre as janelas daquele processo, a que é a sessão — ou None."""
    return casar(_pares_de(janelas, pid), title, directory)


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
        with contextlib.suppress(ProcessLookupError, OSError):
            processo.kill()
        return 124, ""
    return processo.returncode or 0, (saida or b"").decode("utf-8", "replace")


def _escrever(tty: str | None, dados: bytes) -> bool:
    """Escreve na tty da sessão. É o canal que o sino e o título usam: o que sai
    ali é interpretado pelo emulador, não pelo programa que está rodando."""
    if not tty or not tty.startswith("/dev/"):
        return False
    try:
        fd = os.open(tty, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        os.write(fd, dados)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def ring(tty: str | None) -> bool:
    """Toca o sino na tty da sessão: a janela dela pede atenção na barra.

    É o plano B universal — e o único caminho no Wayland quando o terminal não
    fala D-Bus.
    """
    return _escrever(tty, b"\a")


def _limpar_titulo(texto: str) -> str:
    """Título pronto para voltar à tty: sem controles, e curto."""
    return "".join(c for c in texto if c.isprintable())[:300]


def set_title(tty: str | None, texto: str) -> bool:
    """Troca o título da janela pela tty da sessão (OSC 2)."""
    return _escrever(tty, f"\033]2;{_limpar_titulo(texto)}\007".encode("utf-8", "replace"))


class Focuser:
    """Põe na frente a janela de uma sessão. `available` diz se há mecanismo
    além do sino."""

    def __init__(self, method: str | None = ...) -> None:  # type: ignore[assignment]
        self.method = detect() if method is ... else method

    @property
    def available(self) -> bool:
        return bool(self.method)

    async def _window_calls(self, metodo: str, *args: str) -> tuple[int, str]:
        return await _rodar(
            ["gdbus", "call", "--session", "--dest", WINDOW_CALLS[0],
             "--object-path", WINDOW_CALLS[1],
             "--method", f"{WINDOW_CALLS[2]}.{metodo}", *args]
        )

    async def _janelas_window_calls(self) -> list | None:
        """As janelas da sessão gráfica, segundo a extensão Window Calls.

        `None` quer dizer **extensão ausente** (ou muda) — e é informação: é a
        diferença entre "não achei a janela" e "não tenho como achar janela
        nenhuma". Uma lista vazia seria a primeira; None é a segunda.
        """
        código, saida = await self._window_calls("List")
        if código != 0:
            return None
        bruto = _gvariant_string(saida)
        if not bruto:
            return None
        try:
            janelas = json.loads(bruto)
        except ValueError:
            return None
        return janelas if isinstance(janelas, list) else None

    async def _focada(self, janela: int) -> bool:
        """A janela ficou mesmo em foco?

        O `Activate` não devolve erro quando o compositor recusa: quem sabe a
        verdade é a lista, que traz o `focus` de cada janela. Duas olhadas
        porque a troca tem animação, e a primeira pode chegar cedo demais.
        """
        for tentativa in range(2):
            if tentativa:
                await asyncio.sleep(0.3)
            for j in await self._janelas_window_calls() or ():
                if isinstance(j, dict) and j.get("id") == janela:
                    if j.get("focus"):
                        return True
                    break
        return False

    async def _pela_tty(self, tty: str | None, listar) -> object | None:
        """Qual das janelas é esta sessão — perguntando pela tty dela.

        É o único vínculo confiável quando o emulador hospeda várias janelas num
        processo só. O título não serve: numa máquina real ele é de quem está
        rodando na aba — o agente escreve o que está fazendo, um player escreve a
        música, o shell escreve `usuário@host`. Nada disso fala da sessão.

        Mas a tty fala: escrevemos nela um título único (o mesmo canal do sino),
        perguntamos a `listar()` quem está com ele e devolvemos o título de
        antes. Quem não responder ao OSC simplesmente não é encontrado aqui, e o
        caminho segue para o desempate por texto.

        `listar()` devolve `[(id, título)]` — é o que faz isto valer para o
        Window Calls, o wmctrl e o xdotool sem mudar uma linha.
        """
        antes = dict(await listar())
        if len(antes) < 2:
            # Sem ambiguidade não vale mexer no título de ninguém.
            return None
        marca = f"watchai:{os.getpid()}:{time.monotonic_ns():x}"
        if not set_title(tty, marca):
            return None
        for espera in (0.2, 0.3):
            await asyncio.sleep(espera)
            for identificador, titulo in await listar():
                if titulo and marca in titulo:
                    # O agente reescreve o título dele no próximo quadro, mas
                    # até lá a janela não fica com a nossa marca na cara.
                    set_title(tty, antes.get(identificador) or "")
                    return identificador
        # Não achou: ou o terminal ignora o OSC, ou já reescreveu o título por
        # cima. Nos dois casos não há marca nossa pendurada para desfazer.
        return None

    async def _pares_window_calls(self, pid: int) -> list:
        janelas = await self._janelas_window_calls() or []
        return [
            (j.get("id"), j.get("title") or "")
            for j in janelas
            if isinstance(j, dict) and j.get("pid") == pid
        ]

    async def _janela_da_sessao(
        self,
        janelas: list,
        pid: int,
        tty: str | None,
        title: str | None,
        directory: str | None,
    ) -> int | None:
        """A janela desta sessão, do vínculo mais forte para o mais fraco."""
        if len(_pares_de(janelas, pid)) > 1:
            janela = await self._pela_tty(tty, lambda: self._pares_window_calls(pid))
            if janela is not None:
                return janela
        return escolher(janelas, pid, title, directory)

    async def _pares_wmctrl(self, pid: int) -> list:
        código, saida = await _rodar(["wmctrl", "-l", "-p"])
        if código != 0:
            return []
        pares = []
        for linha in saida.splitlines():
            partes = linha.split(None, 4)  # id, área, pid, host, título
            if len(partes) >= 5 and partes[2] == str(pid):
                pares.append((partes[0], partes[4]))
        return pares

    async def _pares_xdotool(self, pid: int) -> list:
        código, saida = await _rodar(["xdotool", "search", "--pid", str(pid)])
        if código != 0:
            return []
        pares = []
        # `search --pid` traz também janelas invisíveis; 20 cobrem qualquer uso
        # real e evitam uma rajada de processos numa sessão cheia.
        for identificador in [i for i in saida.split() if i.strip()][:20]:
            _, nome = await _rodar(["xdotool", "getwindowname", identificador])
            pares.append((identificador, nome.strip()))
        return pares

    async def _janela_wmctrl(self, pid: int, title: str | None, directory: str | None = None):
        """O id da janela daquele processo, pelo desempate fraco."""
        return casar(await self._pares_wmctrl(pid), title, directory)

    async def focus(
        self,
        *,
        pid: int | None = None,
        app: str | None = None,
        tty: str | None = None,
        title: str | None = None,
        directory: str | None = None,
    ) -> str:
        """Tenta focar e devolve, em uma linha, o que conseguiu fazer.

        Só chama de sucesso o que dá para conferir. Um aviso de sucesso que não
        move a janela é pior que um "não consegui": manda você procurar na tela
        o que não está lá.
        """
        dica = ""
        if pid and self.method == "osascript":
            # A marca vai no próprio script: pedir a lista de janelas ao
            # AppleScript e casar aqui seria brigar com nomes que têm vírgula.
            marca = f"watchai:{os.getpid()}:{time.monotonic_ns():x}"
            marcou = set_title(tty, marca)
            if marcou:
                await asyncio.sleep(0.2)
            script = OSASCRIPT.replace("__PID__", str(pid)).replace(
                "__MARCA__", marca if marcou else ""
            )
            código, saida = await _rodar(["osascript", "-e", script], timeout=15.0)
            if marcou:
                # Aqui não dá para devolver o título de antes (ele não foi lido
                # antes da marca): o título vazio faz o Terminal.app e o iTerm2
                # voltarem ao que eles mesmos calculam, e o agente reescreve o
                # dele no próximo quadro.
                set_title(tty, "")
            if código == 0 and "RAISED" in saida:
                return "window raised"
            if "REFUSED" in saida:
                return "the window manager refused to raise the window"
            # Código não-zero aqui costuma ser permissão de Acessibilidade
            # faltando — e aí o sino, abaixo, é o que sobra.
        elif pid and self.method == "powershell":
            exe = shutil.which("powershell") or shutil.which("pwsh")
            if exe:
                # O Add-Type compila na primeira chamada; 5 s seria apertado.
                código, saida = await _rodar(
                    [exe, "-NoProfile", "-NonInteractive", "-Command",
                     POWERSHELL_ACTIVATE.replace("__PID__", str(pid))],
                    timeout=15.0,
                )
                if código == 0 and "RAISED" in saida:
                    return "window raised"
                if "REFUSED" in saida:
                    return "the window manager refused to raise the window"
        elif pid and self.method == "wmctrl":
            janela = await self._pela_tty(tty, lambda: self._pares_wmctrl(pid))
            if janela is None:
                janela = await self._janela_wmctrl(pid, title, directory)
            if janela:
                código, _ = await _rodar(["wmctrl", "-i", "-a", str(janela)])
                if código == 0:
                    return "window raised"
        elif pid and self.method == "xdotool":
            janela = await self._pela_tty(tty, lambda: self._pares_xdotool(pid))
            if janela is None:
                código, saida = await _rodar(["xdotool", "search", "--pid", str(pid)])
                ids = [linha for linha in saida.split() if linha.strip()]
                # A última é a mais recente, que costuma ser a janela de fato.
                janela = ids[-1] if código == 0 and ids else None
            if janela:
                código, _ = await _rodar(["xdotool", "windowactivate", str(janela)])
                if código == 0:
                    return "window raised"
        elif self.method == "gdbus":
            # 1) Window Calls: foco exato, e a única forma precisa no Wayland.
            janelas = await self._janelas_window_calls() if pid else None
            if janelas is None:
                # Sem a extensão não há como escolher janela nem conferir foco.
                dica = " — install Window Calls for real focus" if wayland() and gnome() else ""
            elif pid:
                janela = await self._janela_da_sessao(janelas, pid, tty, title, directory)
                if janela is not None:
                    # Minimizada, a janela ignora o Activate: é preciso
                    # restaurá-la antes. Numa janela normal o Unminimize não faz
                    # nada, então sai barato chamar sempre.
                    await self._window_calls("Unminimize", str(janela))
                    await self._window_calls("Activate", str(janela))
                    if await self._focada(janela):
                        return "window raised"
                    return "the compositor refused to raise the window"
            # 2) Sem a extensão: pedir ao próprio terminal que se levante. No
            #    X11 o pedido é honrado; no Wayland ele volta zero e é ignorado,
            #    e tentar só produziria um sucesso falso — então nem tenta.
            destino = APPS_DBUS.get(app or "")
            if destino and janelas is None and not wayland():
                caminho = "/" + destino.replace(".", "/")
                código, _ = await _rodar(
                    ["gdbus", "call", "--session", "--dest", destino,
                     "--object-path", caminho,
                     "--method", "org.freedesktop.Application.Activate", "{}"]
                )
                if código == 0:
                    # O Activate levanta o app, mas quem escolhe a aba é o
                    # terminal: o sino na tty marca qual delas.
                    if ring(tty):
                        return "terminal raised, tab flagged"
                    return "terminal raised"

        if ring(tty):
            onde = tty.replace("/dev/", "")
            return f"bell rung on {onde}; the window is asking for attention{dica}"
        return f"couldn't reach that window{dica}"


__all__ = [
    "APPS_DBUS",
    "EMULADORES",
    "Focuser",
    "detect",
    "casar",
    "escolher",
    "gnome",
    "ring",
    "set_title",
    "wayland",
]
