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
import time
from dataclasses import dataclass, field
from typing import Protocol

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
    cwd: str | None = None
    tool_children: int = 0  # descendentes que são ferramenta rodando agora
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

    Os terminais vêm junto porque um terminal **sem agente** não aparece na
    lista de agentes — e sem essa lista não dá para distinguir "aba aberta e
    ociosa" de "aba fechada", que é a diferença entre IDLE e OFFLINE.
    """

    agents: tuple[ProcObs, ...] = field(default=())
    terminals: dict[str, TermObs] = field(default_factory=dict)


class ProcessSource(Protocol):
    def snapshot(self) -> Snapshot:
        """O que existe agora. Nunca levanta: erro vira leitura vazia."""
        ...


def rotulo_terminal(tty: str | None, shell_nome: str | None, shell_pid: int | None) -> str:
    if tty:
        return tty.replace("/dev/", "")  # "/dev/pts/10" -> "pts/10"
    if shell_nome and shell_pid:
        return f"{shell_nome} #{shell_pid}"
    return "?"


class PsutilSource:
    """A fonte real. Importa `psutil` na chamada, não no import do módulo —
    assim o app (e a suíte) sobem mesmo sem a dependência instalada."""

    def __init__(self) -> None:
        self._falhou = False

    def snapshot(self) -> Snapshot:
        try:
            import psutil
        except ImportError:
            return Snapshot()
        try:
            return self._varrer(psutil)
        except Exception:
            # Uma varredura que falha não pode derrubar a TUI: a tela apenas
            # não muda até a próxima.
            return Snapshot()

    def _varrer(self, psutil) -> Snapshot:
        agora = time.time()
        eu = os.getuid() if hasattr(os, "getuid") else None
        try:
            usuario = psutil.Process().username()
        except Exception:
            usuario = None

        tabela: dict[int, dict] = {}
        for p in psutil.process_iter(
            ["pid", "ppid", "name", "cmdline", "create_time", "cpu_times", "username", "uids"]
        ):
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
            shell_pid = next(
                (a for a in linha if (tabela[a].get("name") or "").lower().removesuffix(".exe") in SHELLS),
                None,
            )
            nascimento = info.get("create_time") or 0.0
            terminal = tty or (
                f"pid:{shell_pid}:{int(tabela[shell_pid].get('create_time') or 0)}"
                if shell_pid
                else f"pid:{pid}:{int(nascimento)}"
            )
            inicio_terminal = (
                tabela[shell_pid].get("create_time") if shell_pid else nascimento
            ) or nascimento

            filhotes = descendentes(pid)
            cpu = cpu_de(info) + sum(cpu_de(tabela[f]) for f in filhotes if f in tabela)
            ferramentas = sum(
                1
                for f in filhotes
                if f in tabela
                and INFRA_SEGUNDOS
                < (tabela[f].get("create_time") or 0) - nascimento
                and agora - (tabela[f].get("create_time") or 0) < FERRAMENTA_MAX_SEGUNDOS
            )

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
                    ),
                    terminal_started=inicio_terminal,
                    created=nascimento,
                    cpu=cpu,
                    cwd=cwd,
                    tool_children=ferramentas,
                    ancestors=tuple(linha),
                )
            )
        for o in obs:
            terminais.setdefault(
                o.terminal,
                TermObs(key=o.terminal, label=o.terminal_label, started=o.terminal_started),
            )
        return Snapshot(agents=tuple(obs), terminals=terminais)


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
