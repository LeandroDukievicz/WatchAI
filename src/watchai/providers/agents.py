"""Quem é agente de IA e quem só tem o nome parecido.

Casar por "a palavra aparece na linha de comando" produz falso positivo na
hora: um plugin em `~/.claude/plugins/.../telegram` tem "claude" no caminho e
não é agente nenhum. Aqui o casamento é pelo **programa** — o `argv[0]` (ou o
`argv[1]`, quando quem executa é um runtime como `node`/`bun`) — com os
caminhos de pacote como segunda chance, que é o que salva o Windows, onde o
mesmo agente aparece como `node.exe C:\\...\\cli.js`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Runtimes que emprestam o nome ao processo: o agente de verdade é o argumento.
RUNTIMES = frozenset(
    {"node", "bun", "deno", "python", "python3", "py", "uv", "uvx", "npx", "pnpm", "yarn"}
)

# Sufixos que o Windows (e os shims de npm) penduram no executável.
SUFIXOS = (".exe", ".cmd", ".bat", ".ps1", ".js", ".mjs", ".cjs")


@dataclass(frozen=True)
class AgentKind:
    """Assinatura de um agente: como ele se chama e onde ele mora."""

    key: str
    label: str  # como aparece no card
    programas: tuple[str, ...]  # nomes de executável que valem
    pacotes: tuple[str, ...] = field(default=())  # trechos de caminho que valem


KINDS: tuple[AgentKind, ...] = (
    AgentKind("claude", "claude", ("claude",), ("@anthropic-ai/claude-code",)),
    AgentKind("codex", "codex", ("codex",), ("@openai/codex",)),
    AgentKind("gemini", "gemini", ("gemini",), ("@google/gemini-cli",)),
    AgentKind("opencode", "opencode", ("opencode",), ("opencode-ai",)),
    AgentKind("aider", "aider", ("aider",), ("aider_chat", "aider-chat")),
    AgentKind("copilot", "copilot", ("copilot", "github-copilot-cli"), ("@github/copilot",)),
    AgentKind("cursor", "cursor", ("cursor-agent",), ()),
    AgentKind("crush", "crush", ("crush",), ("charmbracelet/crush",)),
    AgentKind("goose", "goose", ("goose",), ("block/goose",)),
    AgentKind("amp", "amp", ("amp",), ("@sourcegraph/amp",)),
)

POR_PROGRAMA = {prog: k for k in KINDS for prog in k.programas}
POR_CHAVE = {k.key: k for k in KINDS}


def _basename(arg: str) -> str:
    """Nome do executável, sem diretório e sem sufixo de plataforma.

    Aceita as duas barras porque a linha de comando pode vir de um Windows
    lido por um WatchAI rodando em qualquer lugar.
    """
    nome = re.split(r"[\\/]", arg.strip().strip('"'))[-1].lower()
    for sufixo in SUFIXOS:
        if nome.endswith(sufixo):
            nome = nome[: -len(sufixo)]
            break
    return nome


def identify(cmdline: list[str] | None) -> AgentKind | None:
    """O agente por trás desta linha de comando, ou None se não for um.

    Ordem: o programa executado, depois o argumento do runtime, e só então o
    caminho do pacote — nessa ordem porque as duas primeiras são exatas e a
    terceira é a que pode confundir.
    """
    if not cmdline:
        return None
    argv = [a for a in cmdline if a]
    if not argv:
        return None

    programa = _basename(argv[0])
    if programa in POR_PROGRAMA:
        return POR_PROGRAMA[programa]

    if programa in RUNTIMES:
        for arg in argv[1:]:
            if arg.startswith("-"):
                continue  # flag do runtime (node --flag script)
            alvo = _basename(arg)
            if alvo in POR_PROGRAMA:
                return POR_PROGRAMA[alvo]
            break  # só o primeiro argumento não-flag é o script

    # Última chance: o caminho do pacote instalado (o caso do Windows, onde o
    # processo é `node.exe` e o nome do agente só existe dentro do caminho).
    # A barra invertida vira barra aqui e não em `os.sep`: quem lê pode estar
    # em Linux olhando uma linha de comando escrita com convenção do Windows.
    linha = " ".join(argv).replace("\\", "/").lower()
    for kind in KINDS:
        if any(p.lower() in linha for p in kind.pacotes):
            return kind
    return None


__all__ = ["AgentKind", "KINDS", "POR_CHAVE", "identify"]
