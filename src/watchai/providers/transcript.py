"""O que cada agente está fazendo — lido do diário que ele mesmo grava.

Claude Code e Codex escrevem um `.jsonl` por sessão no seu disco. Ler esse
arquivo **não é integração**: não há API, hook, credencial nem configuração do
agente envolvida — é o mesmo que olhar um log.

É daqui que sai a distinção que o processo sozinho não dá:

* última entrada é texto do assistente  → **READY** (terminou, é a sua vez);
* é um erro de API (limite de sessão, token expirado) → **ERROR**;
* é uma chamada de ferramenta sem resposta → ferramenta pendente: **WORKING**
  se o processo está gastando CPU, **INPUT** se está parado (ou seja, travado
  esperando você confirmar);
* é o resultado de uma ferramenta → **WORKING** (o modelo voltou a pensar).

Nada aqui pode levantar: arquivo ausente, corrompido ou em formato novo vira
`None`, e o provider cai nos sinais de processo.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Quanto lemos do fim do arquivo. Uma entrada de transcript raramente passa de
# alguns KB; 64 KB cobrem várias com folga.
CAUDA_BYTES = 64 * 1024

# "Pensando" há mais de dois minutos sem nada novo no arquivo não é pensar: é
# um diário parado. Aí o processo decide.
FRESCOR_SEGUNDOS = 120.0

# Estados que o diário sabe dizer.
FEITO = "done"
PENSANDO = "thinking"
FERRAMENTA = "tool_pending"
ERRO = "error"


@dataclass(frozen=True)
class Leitura:
    estado: str  # FEITO | PENSANDO | FERRAMENTA | ERRO
    atividade: str
    mtime: float
    desde: float | None = None  # quando o estado começou, segundo o diário

    def fresca(self, agora: float) -> bool:
        return agora - self.mtime <= FRESCOR_SEGUNDOS


def _epoch(carimbo) -> float | None:
    """ISO-8601 do diário -> epoch. O `Z` do fim é UTC, que o Python < 3.11
    não aceita direto."""
    if not isinstance(carimbo, str) or not carimbo:
        return None
    try:
        return datetime.fromisoformat(carimbo.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _epoch_ms(valor) -> float | None:
    """O OpenCode carimba em milissegundos; o resto do mundo, em segundos."""
    if isinstance(valor, (int, float)) and valor > 0:
        return valor / 1000 if valor > 1e11 else float(valor)
    return None


def _texto(conteudo) -> str:
    """O texto de uma mensagem, venha ela como string ou como blocos."""
    if isinstance(conteudo, str):
        return " ".join(conteudo.split())
    if isinstance(conteudo, list):
        partes = [b.get("text", "") for b in conteudo if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(" ".join(partes).split())
    return ""


def _tail(caminho: Path, limite: int = CAUDA_BYTES) -> list[dict]:
    """As últimas entradas JSON do arquivo, da mais antiga para a mais nova."""
    try:
        with caminho.open("rb") as f:
            f.seek(0, os.SEEK_END)
            tamanho = f.tell()
            f.seek(max(0, tamanho - limite))
            bruto = f.read()
    except OSError:
        return []
    linhas = bruto.split(b"\n")
    if len(linhas) > 1 and tamanho > limite:
        linhas = linhas[1:]  # a primeira veio cortada ao meio
    saida = []
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        try:
            entrada = json.loads(linha)
        except ValueError:
            continue
        if isinstance(entrada, dict):
            saida.append(entrada)
    return saida


def _primeira_linha(caminho: Path) -> dict | None:
    try:
        with caminho.open("r", encoding="utf-8", errors="replace") as f:
            return json.loads(f.readline() or "{}")
    except (OSError, ValueError):
        return None


def _detalhe(entrada: dict | None, limite: int = 38) -> str:
    """Um pedaço legível do argumento da ferramenta: o comando, o arquivo…"""
    if not isinstance(entrada, dict):
        return ""
    for chave in ("command", "file_path", "path", "pattern", "description", "query", "prompt"):
        valor = entrada.get(chave)
        if isinstance(valor, str) and valor.strip():
            texto = " ".join(valor.split())
            return texto[: limite - 1] + "…" if len(texto) > limite else texto
    return ""


class ClaudeCode:
    """`~/.claude/projects/<slug>/<sessão>.jsonl`."""

    kind = "claude"

    def __init__(self, home: Path) -> None:
        self.raiz = home / ".claude" / "projects"

    def arquivo(self, cwd: str) -> Path | None:
        if not self.raiz.is_dir():
            return None
        # O slug é o caminho com os separadores virados em "-". Em vez de
        # reproduzir a regra de cada sistema, tentamos o slug e, se não houver,
        # procuramos pelo `cwd` que o próprio arquivo grava.
        slug = "-" + cwd.strip("/\\").replace("/", "-").replace("\\", "-").replace(":", "-")
        candidatos = []
        direto = self.raiz / slug
        if direto.is_dir():
            candidatos = sorted(direto.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidatos:
            todos = sorted(
                self.raiz.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
            )[:40]
            candidatos = [p for p in todos if (_primeira_linha(p) or {}).get("cwd") == cwd]
        return candidatos[0] if candidatos else None

    def ler(self, caminho: Path) -> Leitura | None:
        entradas = _tail(caminho)
        if not entradas:
            return None
        mtime = caminho.stat().st_mtime
        pendentes: dict[str, tuple[str, str, float | None]] = {}  # id -> (nome, detalhe, quando)
        ultimo = None  # (estado, atividade, quando)
        for entrada in entradas:
            tipo = entrada.get("type")
            if tipo not in ("assistant", "user"):
                continue
            quando = _epoch(entrada.get("timestamp"))
            conteudo = entrada.get("message", {}).get("content")
            # Erro de API (limite de sessão, token expirado): a sessão parou e
            # não volta sozinha — é o que o ERROR existe para avisar.
            if entrada.get("isApiErrorMessage"):
                texto = _texto(conteudo) or "API error"
                pendentes.clear()
                ultimo = (ERRO, texto[:60], quando)
                continue
            if isinstance(conteudo, str):
                ultimo = (FEITO, "task completed", quando)
                continue
            if not isinstance(conteudo, list):
                continue
            for bloco in conteudo:
                kind = bloco.get("type")
                if kind == "tool_use":
                    pendentes[bloco.get("id", "")] = (
                        bloco.get("name", "tool"),
                        _detalhe(bloco.get("input")),
                        quando,
                    )
                    ultimo = None
                elif kind == "tool_result":
                    pendentes.pop(bloco.get("tool_use_id", ""), None)
                    ultimo = (PENSANDO, "thinking", quando)
                elif kind == "text" and entrada.get("type") == "assistant":
                    ultimo = (FEITO, "task completed", quando)
        if pendentes:
            ferramenta, detalhe, quando = next(reversed(list(pendentes.values())))
            texto = f"{ferramenta}: {detalhe}" if detalhe else ferramenta
            return Leitura(FERRAMENTA, texto, mtime, quando)
        if ultimo is None:
            return None
        return Leitura(ultimo[0], ultimo[1], mtime, ultimo[2])


class Codex:
    """`~/.codex/sessions/AAAA/MM/DD/rollout-*.jsonl` — traz eventos explícitos."""

    kind = "codex"

    EVENTOS = {
        "task_complete": (FEITO, "task completed"),
        "task_started": (PENSANDO, "thinking"),
        "error": (ERRO, "error"),
        "stream_error": (ERRO, "stream error"),
    }
    APROVACAO = ("approval_request", "exec_approval", "patch_approval")

    def __init__(self, home: Path) -> None:
        self.raiz = home / ".codex" / "sessions"

    def arquivo(self, cwd: str) -> Path | None:
        if not self.raiz.is_dir():
            return None
        arquivos = sorted(
            self.raiz.glob("*/*/*/rollout-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:40]
        for caminho in arquivos:
            cabeca = _primeira_linha(caminho) or {}
            if (cabeca.get("payload") or {}).get("cwd") == cwd:
                return caminho
        return None

    def ler(self, caminho: Path) -> Leitura | None:
        entradas = _tail(caminho)
        if not entradas:
            return None
        mtime = caminho.stat().st_mtime
        for entrada in reversed(entradas):
            payload = entrada.get("payload") or {}
            tipo = payload.get("type") or ""
            quando = _epoch(entrada.get("timestamp"))
            if any(a in tipo for a in self.APROVACAO):
                return Leitura(FERRAMENTA, "waiting for approval", mtime, quando)
            if tipo in self.EVENTOS:
                estado, atividade = self.EVENTOS[tipo]
                return Leitura(estado, atividade, mtime, quando)
            if tipo in ("function_call", "local_shell_call", "custom_tool_call"):
                detalhe = _detalhe(payload.get("arguments") if isinstance(payload.get("arguments"), dict) else None)
                nome = payload.get("name") or "tool"
                return Leitura(FERRAMENTA, f"{nome}: {detalhe}" if detalhe else nome, mtime, quando)
        return None


class OpenCode:
    """`~/.local/share/opencode/storage/session/{info,message,part}/`.

    ⚠️ **Escrito a partir do layout encontrado no binário do OpenCode, não
    validado contra uma sessão real** — a instalação desta máquina não gravou
    sessão nenhuma desde a migração de storage. Por isso cada acesso é
    defensivo: o que não bater com o esperado devolve `None` e o agente cai na
    camada de processos, que é o comportamento de hoje.
    """

    kind = "opencode"

    def __init__(self, home: Path) -> None:
        self.raiz = home / ".local" / "share" / "opencode" / "storage" / "session"

    def _info(self) -> Path:
        return self.raiz / "info"

    def arquivo(self, cwd: str) -> Path | None:
        pasta = self._info()
        if not pasta.is_dir():
            return None
        candidatos = sorted(pasta.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for caminho in candidatos[:40]:
            dados = _primeira_linha(caminho) or {}
            # O campo do diretório já se chamou "directory" e "cwd"; aceitamos
            # os dois para não quebrar na próxima versão.
            if dados.get("directory") == cwd or dados.get("cwd") == cwd:
                return caminho
        return None

    def ler(self, caminho: Path) -> Leitura | None:
        info = _primeira_linha(caminho) or {}
        sessao = info.get("id") or caminho.stem
        mensagens = self.raiz / "message" / sessao
        if not mensagens.is_dir():
            return None
        try:
            ultima = max(mensagens.glob("*.json"), key=lambda p: p.stat().st_mtime)
        except ValueError:
            return None
        mtime = ultima.stat().st_mtime
        msg = _primeira_linha(ultima) or {}
        quando = _epoch_ms(((msg.get("time") or {}).get("created")))

        # Uma ferramenta ainda rodando aparece nas "partes" da mensagem.
        partes = self.raiz / "part" / sessao / ultima.stem
        if partes.is_dir():
            for parte in sorted(partes.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                dados = _primeira_linha(parte) or {}
                if dados.get("type") != "tool":
                    continue
                estado = (dados.get("state") or {}).get("status")
                nome = dados.get("tool") or "tool"
                if estado in ("running", "pending"):
                    detalhe = _detalhe((dados.get("state") or {}).get("input"))
                    return Leitura(
                        FERRAMENTA, f"{nome}: {detalhe}" if detalhe else nome, mtime, quando
                    )
                if estado == "error":
                    return Leitura(ERRO, f"{nome} failed", mtime, quando)
                break  # a parte mais recente já respondeu

        if msg.get("role") == "assistant":
            terminou = (msg.get("time") or {}).get("completed")
            if terminou:
                return Leitura(FEITO, "task completed", mtime, _epoch_ms(terminou) or quando)
            return Leitura(PENSANDO, "thinking", mtime, quando)
        return Leitura(PENSANDO, "thinking", mtime, quando)


class Transcripts:
    """Resolve o diário de cada agente e guarda o que já leu.

    O casamento é por diretório de trabalho: o mesmo `cwd` que o processo
    expõe é o que o agente grava no arquivo. Dois agentes do mesmo tipo no
    mesmo diretório compartilham o diário mais recente — o segundo cai nos
    sinais de processo, que é a degradação certa.
    """

    def __init__(self, home: Path | None = None) -> None:
        raiz = home or Path.home()
        self.leitores = {r.kind: r for r in (ClaudeCode(raiz), Codex(raiz), OpenCode(raiz))}
        self._arquivo: dict[tuple[str, str], Path | None] = {}
        self._cache: dict[Path, tuple[float, Leitura | None]] = {}

    def ler(self, kind: str, cwd: str | None) -> Leitura | None:
        leitor = self.leitores.get(kind)
        if leitor is None or not cwd:
            return None
        try:
            chave = (kind, cwd)
            caminho = self._arquivo.get(chave, ...)
            if caminho is ... or (caminho is not None and not caminho.exists()):
                caminho = leitor.arquivo(cwd)
                self._arquivo[chave] = caminho
            if caminho is None:
                return None
            mtime = caminho.stat().st_mtime
            anterior = self._cache.get(caminho)
            if anterior is not None and anterior[0] == mtime:
                return anterior[1]  # nada mudou: não relê o arquivo
            leitura = leitor.ler(caminho)
            self._cache[caminho] = (mtime, leitura)
            return leitura
        except OSError:
            return None

    def esquecer(self, kind: str, cwd: str) -> None:
        self._arquivo.pop((kind, cwd), None)


__all__ = [
    "ERRO",
    "FEITO",
    "FERRAMENTA",
    "FRESCOR_SEGUNDOS",
    "Leitura",
    "PENSANDO",
    "Transcripts",
]
