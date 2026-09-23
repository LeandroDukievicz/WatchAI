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


# O registro de agentes conhecidos. Vale para quem instalar o WatchAI em
# qualquer lugar, não só para quem já tem os mesmos CLIs que você — por isso ele
# é amplo e conservador ao mesmo tempo:
#
# * **programa** é casamento exato pelo nome do executável (`argv[0]`, ou
#   `argv[1]` quando quem executa é um runtime). É o critério confiável.
# * **pacote** é um trecho de caminho, usado só quando o nome do processo não
#   diz nada — o caso do Windows, onde tudo vira `node.exe`. Tem que ser
#   específico (`@openai/codex`), nunca uma palavra solta: "deepseek" no caminho
#   pegaria um `ollama run deepseek-r1`, que não é sessão de agente nenhuma.
#
# Falta algum? Não espere uma release: acrescente no seu
# `~/.config/watchai/config.json` (veja `config.load_agents`) — e, se for um
# agente conhecido, mande um PR para esta tabela.
KINDS: tuple[AgentKind, ...] = (
    AgentKind("claude", "claude", ("claude",), ("@anthropic-ai/claude-code",)),
    AgentKind("codex", "codex", ("codex",), ("@openai/codex",)),
    AgentKind("gemini", "gemini", ("gemini",), ("@google/gemini-cli",)),
    # O executável do Antigravity CLI se chama `agy` — nome curto e nada óbvio,
    # e um binário nativo, sem caminho de pacote que sirva de segunda chance.
    # Sem ele na lista, a sessão simplesmente não aparecia.
    AgentKind(
        "antigravity",
        "antigravity",
        ("agy", "antigravity", "antigravity-cli"),
        ("antigravity-cli",),
    ),
    AgentKind("opencode", "opencode", ("opencode",), ("opencode-ai",)),
    AgentKind("aider", "aider", ("aider",), ("aider_chat", "aider-chat")),
    AgentKind("copilot", "copilot", ("copilot", "github-copilot-cli"), ("@github/copilot",)),
    AgentKind("grok", "grok", ("grok", "grok-cli"), ("@vibe-kit/grok-cli",)),
    AgentKind("deepseek", "deepseek", ("deepseek", "deepseek-cli"), ()),
    AgentKind("qwen", "qwen", ("qwen", "qwen-code"), ("@qwen-code/qwen-code",)),
    AgentKind("cursor", "cursor", ("cursor-agent",), ()),
    AgentKind("crush", "crush", ("crush",), ("charmbracelet/crush",)),
    AgentKind("goose", "goose", ("goose",), ("block/goose",)),
    AgentKind("amp", "amp", ("amp",), ("@sourcegraph/amp",)),
    AgentKind("openhands", "openhands", ("openhands",), ("openhands-ai",)),
    AgentKind("plandex", "plandex", ("plandex",), ()),
    AgentKind("continue", "continue", ("continue",), ("@continuedev/cli",)),
)

# Invocações em duas palavras: o agente é um subcomando de outro programa.
SUBCOMANDOS = {("gh", "copilot"): "copilot"}

POR_CHAVE: dict[str, AgentKind] = {k.key: k for k in KINDS}
POR_PROGRAMA: dict[str, AgentKind] = {prog: k for k in KINDS for prog in k.programas}


def registrar(extras: dict[str, list[str]] | None) -> list[str]:
    """Acrescenta agentes definidos pelo usuário: `{"meu-agente": ["meuprog"]}`.

    O ecossistema ganha CLI nova toda semana e ninguém deveria esperar uma
    release para ver a própria sessão na tela. Nome já conhecido é reforçado
    (mais um apelido para o mesmo agente); nome novo cria um tipo.

    Devolve as chaves que passaram a valer, para quem quiser conferir.
    """
    if not extras:
        return []
    aceitos = []
    for chave, programas in extras.items():
        chave = str(chave).strip().lower()
        if not chave:
            continue
        nomes = tuple(
            _basename(str(p)) for p in (programas or ()) if str(p).strip()
        ) or (chave,)
        base = POR_CHAVE.get(chave)
        kind = AgentKind(
            chave,
            base.label if base else chave,
            tuple(dict.fromkeys((*(base.programas if base else ()), *nomes))),
            base.pacotes if base else (),
        )
        POR_CHAVE[chave] = kind
        for nome in kind.programas:
            POR_PROGRAMA[nome] = kind
        aceitos.append(chave)
    return aceitos


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

    # Subcomando: `gh copilot`, onde o agente não é o programa executado.
    if len(argv) > 1:
        chave = SUBCOMANDOS.get((programa, _basename(argv[1])))
        if chave:
            return POR_CHAVE[chave]

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


__all__ = ["AgentKind", "KINDS", "POR_CHAVE", "SUBCOMANDOS", "identify", "registrar"]
