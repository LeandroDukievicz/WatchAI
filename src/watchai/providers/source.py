"""De onde vêm os processos — a única parte que conhece o sistema operacional.

`ProcessSource` é o contrato; `PsutilSource` é a implementação real. Os testes
injetam uma fonte falsa e nunca tocam na tabela de processos da máquina.

O que é portátil e o que não é:

| sinal                       | Linux | macOS | Windows |
|-----------------------------|-------|-------|---------|
| pid, cmdline, início, CPU   |  sim  |  sim  |   sim   |
| cwd do processo             |  sim  | só os seus | sim |
| tty (identidade do terminal)|  sim  |  sim  |  não existe |

Sem tty (Windows), a identidade do terminal vira o **shell ancestral** — que é
o análogo certo: cada aba do Windows Terminal abre o seu próprio shell.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Protocol

from ..focus import EMULADORES
from .agents import identify

# Um filho criado logo depois do agente é infraestrutura dele (servidor MCP,
# plugin, host de ferramentas); criado bem depois, é ferramenta rodando agora.
INFRA_SEGUNDOS = 30.0

# ...mas só conta como ferramenta enquanto for jovem: o `codex` mantém um host
# auxiliar que nasce dois minutos depois dele e vive dias — sem este teto, a
# sessão ficaria eternamente "trabalhando". Ferramenta longa e de verdade
# aparece na CPU da árvore, que é o outro sinal.
FERRAMENTA_MAX_SEGUNDOS = 600.0

SHELLS = frozenset(
    {"bash", "zsh", "fish", "sh", "dash", "ksh", "tcsh", "csh",
     "pwsh", "powershell", "cmd", "nu", "elvish", "xonsh"}
)


@dataclass(frozen=True)
class ProcObs:
    """Um agente visto uma vez, com o que dá para medir sem hook nenhum."""

    pid: int
    kind: str  # chave do AgentKind: "claude", "codex", ...
    label: str  # como aparece no card: "claude"
    terminal: str  # identidade do terminal: "/dev/pts/10" ou "pid:4312:17..."
    terminal_label: str  # "pts/10", "pwsh #4312"
    terminal_started: float  # epoch: quando o terminal (ou o agente) nasceu
    created: float  # epoch do processo
    cpu: float  # segundos de CPU acumulados pelo agente + descendentes
    # Só o do processo do agente. A árvore inclui o que ele abriu e não
    # fechou — um navegador, um servidor de desenvolvimento —, e isso mede a
    # sessão trabalhando só enquanto o diário disser que há rodada aberta.
    cpu_proprio: float = 0.0
    cwd: str | None = None
    tool_children: int = 0  # descendentes que são ferramenta rodando agora
    tool_label: str = ""  # a ferramenta mais recente ("npm test", "rg foo")
    window_pid: int | None = None  # processo que **tem a janela** (o emulador)
    window_app: str = ""  # nome dele: "gnome-terminal-server", "ptyxis"…
    ancestors: tuple[int, ...] = field(default=())  # para desduplicar por árvore


@dataclass(frozen=True)
class TermObs:
    """Um terminal interativo aberto agora."""

    key: str
    label: str
    started: float


@dataclass(frozen=True)
class Snapshot:
    """Uma leitura do sistema: os agentes e os terminais que existem agora.

    Os terminais vêm junto porque o agente não sabe a hora em que a aba abriu
    — ele nasce depois dela — e é essa hora que o card mostra como "elapsed".
    """

    agents: tuple[ProcObs, ...] = field(default=())
    terminals: dict[str, TermObs] = field(default_factory=dict)
    # Por que a leitura veio vazia, quando veio. Lista vazia e lista impossível
    # de ler são coisas diferentes, e a tela precisa dizer qual das duas é:
    # "" (leu normalmente) · "sem-psutil" · "restrito" · "erro".
    diagnostico: str = ""


class ProcessSource(Protocol):
    def snapshot(self) -> Snapshot:
        """O que existe agora. Nunca levanta: erro vira leitura vazia."""
        ...


def rotulo_terminal(
    tty: str | None,
    shell_nome: str | None,
    shell_pid: int | None,
    agente: str = "",
    pid: int | None = None,
) -> str:
    """Como o card chama o "terminal" da sessão.

    Nem todo agente roda numa tty: dentro de uma IDE não há terminal nenhum, e
    aí o que identifica a sessão é o próprio processo.
    """
    if tty:
        return tty.replace("/dev/", "")  # "/dev/pts/10" -> "pts/10"
    if shell_nome and shell_pid:
        return f"{shell_nome} #{shell_pid}"
    if agente and pid:
        return f"{agente} #{pid}"
    return "?"


# Quantos processos uma máquina de verdade mostra. Abaixo disto, não é que não
# haja o que ver: é que não estamos conseguindo ver — confinamento de Snap ou
# Flatpak, container, `hidepid`. Qualquer sistema com uma sessão gráfica aberta
# passa de dezenas.
PROCESSOS_PLAUSIVEIS = 8


class PsutilSource:
    """A fonte real. Importa `psutil` na chamada, não no import do módulo —
    assim o app (e a suíte) sobem mesmo sem a dependência instalada."""

    def __init__(self) -> None:
        self._falhou = False

    def snapshot(self) -> Snapshot:
        try:
            import psutil
        except ImportError:
            # Sem a dependência não há o que ler — e isso tem conserto de uma
            # linha, desde que alguém diga qual.
            return Snapshot(diagnostico="sem-psutil")
        try:
            return self._varrer(psutil)
        except Exception:
            # Uma varredura que falha não pode derrubar a TUI: a tela apenas
            # não muda até a próxima.
            return Snapshot(diagnostico="erro")

    def _varrer(self, psutil) -> Snapshot:
        agora = time.time()
        eu = os.getuid() if hasattr(os, "getuid") else None
        try:
            usuario = psutil.Process().username()
        except Exception:
            usuario = None

        tabela: dict[int, dict] = {}
        vistos = 0  # antes de filtrar por usuário: mede o que dá para enxergar
        for p in psutil.process_iter(
            ["pid", "ppid", "name", "cmdline", "create_time", "cpu_times", "username", "uids"]
        ):
            vistos += 1
            info = p.info
            if eu is not None:
                uids = info.get("uids")
                if uids is not None and uids.real != eu:
                    continue
            elif usuario is not None and info.get("username") not in (None, usuario):
                continue
            tabela[info["pid"]] = info

        filhos: dict[int, list[int]] = {}
        for pid, info in tabela.items():
            filhos.setdefault(info.get("ppid") or 0, []).append(pid)

        def cpu_de(info: dict) -> float:
            t = info.get("cpu_times")
            return (t.user + t.system) if t else 0.0

        def descendentes(raiz: int) -> list[int]:
            fila, saida = list(filhos.get(raiz, ())), []
            while fila:
                pid = fila.pop()
                saida.append(pid)
                fila.extend(filhos.get(pid, ()))
            return saida

        def ancestrais(pid: int) -> list[int]:
            saida, atual = [], tabela.get(pid, {}).get("ppid")
            while atual and atual in tabela and len(saida) < 32:
                saida.append(atual)
                atual = tabela[atual].get("ppid")
            return saida

        # Terminais interativos: um shell com tty (Unix) é uma aba aberta; no
        # Windows não há tty, então o próprio shell é a identidade.
        terminais: dict[str, TermObs] = {}
        for pid, info in tabela.items():
            nome = (info.get("name") or "").lower().removesuffix(".exe")
            if nome not in SHELLS:
                continue
            try:
                tty = psutil.Process(pid).terminal()
            except Exception:
                tty = None
            nascimento = info.get("create_time") or 0.0
            key = tty or f"pid:{pid}:{int(nascimento)}"
            atual = terminais.get(key)
            # Vários shells na mesma tty (sub-shells): vale o mais antigo, que
            # é quem representa a abertura da aba.
            if atual is None or nascimento < atual.started:
                terminais[key] = TermObs(
                    key=key, label=rotulo_terminal(tty, nome, pid), started=nascimento
                )

        obs: list[ProcObs] = []
        for pid, info in tabela.items():
            kind = identify(info.get("cmdline"))
            if kind is None:
                continue
            proc = psutil.Process(pid)
            try:
                tty = proc.terminal() if hasattr(proc, "terminal") else None
            except Exception:
                tty = None
            try:
                cwd = proc.cwd()
            except Exception:
                cwd = None  # macOS pode negar; o transcript tem o cwd de reserva

            linha = ancestrais(pid)
            def nome_de(pid_: int) -> str:
                return (tabela[pid_].get("name") or "").lower().removesuffix(".exe")

            shell_pid = next((a for a in linha if nome_de(a) in SHELLS), None)
            # Quem desenha a janela é o emulador, alguns níveis acima do shell:
            # é o PID que os gerenciadores de janela conhecem.
            janela_pid = next((a for a in linha if nome_de(a) in EMULADORES), None)
            nascimento = info.get("create_time") or 0.0
            terminal = tty or (
                f"pid:{shell_pid}:{int(tabela[shell_pid].get('create_time') or 0)}"
                if shell_pid
                else f"pid:{pid}:{int(nascimento)}"
            )
            inicio_terminal = (
                tabela[shell_pid].get("create_time") if shell_pid else nascimento
            ) or nascimento

            def rotulo_ferramenta(info_filho: dict) -> str:
                """O que a ferramenta é, em poucas palavras — é isso que vira a
                atividade de um agente que não tem diário para ler."""
                argv = [a for a in (info_filho.get("cmdline") or []) if a]
                if not argv:
                    return info_filho.get("name") or ""
                nome = re.split(r"[\\/]", argv[0])[-1]
                if nome.removesuffix(".exe") in SHELLS and len(argv) > 2 and argv[1] in ("-c", "/c", "-lc"):
                    # O shell é só o envelope. E o Claude Code embrulha o
                    # comando num `eval '...'` depois de carregar o snapshot do
                    # ambiente: o que interessa é o que vem depois do eval.
                    texto = argv[2]
                    if "eval '" in texto:
                        texto = texto.split("eval '", 1)[1].rstrip("'")
                else:
                    texto = " ".join([nome, *argv[1:]])
                texto = " ".join(texto.split())
                return texto[:37] + "…" if len(texto) > 38 else texto

            filhotes = descendentes(pid)
            cpu_proprio = cpu_de(info)
            cpu = cpu_proprio + sum(cpu_de(tabela[f]) for f in filhotes if f in tabela)
            ferramentas_vivas = [
                f
                for f in filhotes
                if f in tabela
                and INFRA_SEGUNDOS
                < (tabela[f].get("create_time") or 0) - nascimento
                and agora - (tabela[f].get("create_time") or 0) < FERRAMENTA_MAX_SEGUNDOS
                # Processo auxiliar do próprio agente (o host de ferramentas do
                # codex, por exemplo) é infraestrutura, não ferramenta rodando.
                and identify(tabela[f].get("cmdline")) is None
            ]
            ferramentas = len(ferramentas_vivas)
            rotulo = ""
            if ferramentas_vivas:
                # A mais nova é a que está acontecendo agora.
                recente = max(ferramentas_vivas, key=lambda f: tabela[f].get("create_time") or 0)
                rotulo = rotulo_ferramenta(tabela[recente])

            obs.append(
                ProcObs(
                    pid=pid,
                    kind=kind.key,
                    label=kind.label,
                    terminal=terminal,
                    terminal_label=rotulo_terminal(
                        tty,
                        (tabela[shell_pid].get("name") if shell_pid else None),
                        shell_pid,
                        kind.label,
                        pid,
                    ),
                    terminal_started=inicio_terminal,
                    created=nascimento,
                    cpu=cpu,
                    cpu_proprio=cpu_proprio,
                    cwd=cwd,
                    tool_children=ferramentas,
                    tool_label=rotulo,
                    window_pid=janela_pid or shell_pid,
                    window_app=nome_de(janela_pid) if janela_pid else "",
                    ancestors=tuple(linha),
                )
            )
        for o in obs:
            terminais.setdefault(
                o.terminal,
                TermObs(key=o.terminal, label=o.terminal_label, started=o.terminal_started),
            )
        return Snapshot(
            agents=tuple(obs),
            terminals=terminais,
            diagnostico="restrito" if vistos < PROCESSOS_PLAUSIVEIS else "",
        )


__all__ = [
    "FERRAMENTA_MAX_SEGUNDOS",
    "INFRA_SEGUNDOS",
    "ProcObs",
    "ProcessSource",
    "PsutilSource",
    "Snapshot",
    "TermObs",
    "rotulo_terminal",
]
