"""Quanto já foi gasto das janelas de limite do plano.

Duas janelas, iguais nos dois agentes: uma **curta** (5 h) e uma **longa**
(7 dias). De onde vem cada número:

* **codex** — já está no disco, sem configuração nenhuma. O mesmo
  `rollout-*.jsonl` que o leitor de diário abre traz, numa entrada
  `payload.type == "token_count"`, um bloco `rate_limits` com `used_percent`,
  `window_minutes` e `resets_at`;
* **Claude Code** — **não grava limite em lugar nenhum** (varredura completa de
  `~/.claude`: nem `rate_limit`, nem `quota`, nem `utilization`). Mas ele
  **empurra** o dado para scripts de statusline desde a 2.1.80. Então o WatchAI
  não puxa: quem escreve é o `watchai --statusline`, que o agente chama, e o app
  segue lendo só arquivo local — que é a regra do produto.

O que este módulo **não** faz, de propósito:

* **não deriva percentual somando tokens.** O mapeamento de tokens para o limite
  da Anthropic não é público e varia por modelo e plano: o número sairia
  inventado, que é justamente o erro que o projeto evita;
* **não chama API e não lê credencial.** `~/.claude/.credentials.json` guarda o
  token OAuth em modo 600 e tem um `rateLimitTier` dentro. Não encostamos: isto
  não é preferência, é regra;
* **não confere** o número. O rollout do codex é legível e editável — um `sed`
  muda o percentual. Isso não dá cota (o arquivo é o registro do que o servidor
  respondeu, não onde o limite é conferido), mas significa que o WatchAI não tem
  como verificar. A resposta é rótulo honesto mais **validação de faixa**, com a
  **idade do dado à vista**: o número é tão fresco quanto o último uso daquele
  agente, e número velho com cara de vivo é o pior dos dois mundos.

Nada aqui pode levantar: arquivo ausente, corrompido ou em formato novo vira
`None`, e a barra simplesmente não aparece.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .transcript import _epoch, _por_mtime, _tail

# Quantos rollouts recentes do codex vale abrir procurando o último
# `token_count`. Mais de um porque **sessão nova não tem**: o bloco só é escrito
# depois da primeira resposta do servidor, e o rollout de uma sessão que acabou
# de abrir não traz nenhum. Sem isto, abrir um codex apagava a barra.
ARQUIVOS_VISTOS = 10

# De quanto em quanto tempo os leitores rodam. Limite de plano não muda a cada
# dois segundos, e a varredura de processos não pode ficar mais cara por isto.
INTERVALO = 30.0

# Até aqui a janela é a "curta" (5 h = 300 min); acima, a "longa" (7 d = 10080).
# A fronteira é generosa de propósito: quem mudar o tamanho das janelas continua
# caindo no lado certo.
CURTA_MAX_MINUTOS = 24 * 60

# Faixas plausíveis. Fora delas o campo é descartado em vez de virar tela.
EPOCH_MIN = 1_577_836_800.0  # 2020-01-01
EPOCH_MAX = 4_102_444_800.0  # 2100-01-01
JANELA_MAX_MINUTOS = 366 * 24 * 60

# Percentual acima disto merece cor: amarelo quando aperta, vermelho quando
# está no fim. Quem decide a cor é o widget; o limiar mora aqui porque é
# decisão de produto, não de desenho.
APERTA = 75.0
ESTOURANDO = 90.0

# Dado mais velho que isto tem a idade mostrada junto. Abaixo, é "agora" para
# qualquer efeito prático e a idade só faria ruído.
IDADE_VISIVEL = 300.0

# O nome do percentual **diverge entre os dois**: `used_percent` no codex,
# `used_percentage` no Claude Code. O normalizador aceita os dois — e é este o
# tipo de detalhe que, esquecido, faz a barra do Claude nunca aparecer.
CAMPOS_USADO = ("used_percent", "used_percentage", "utilization", "used")
CAMPOS_MINUTOS = ("window_minutes", "window_size_minutes", "window")
CAMPOS_RESET = ("resets_at", "reset_at", "resets_at_seconds", "resetsAt")

# Tamanho suposto quando o bloco **não** traz `window_minutes`. Quem classifica
# é sempre o tamanho, e o codex informa o dele; isto é para o Claude Code, cujo
# campo é novo e do qual o changelog promete só as duas janelas ("5-hour and
# 7-day windows with `used_percentage` and `resets_at`") — se ele nomear em vez
# de medir, o nome ainda diz qual é qual. Nome desconhecido e sem tamanho fica
# de fora: janela que não se sabe medir não vira barra.
MINUTOS_POR_NOME = {
    "primary": 300,
    "five_hour": 300,
    "fivehour": 300,
    "5h": 300,
    "short": 300,
    "secondary": 10080,
    "seven_day": 10080,
    "sevenday": 10080,
    "7d": 10080,
    "week": 10080,
    "weekly": 10080,
    "long": 10080,
}

# Blocos de `rate_limits` que não são janela — ignorá-los pelo nome evita que um
# campo novo do agente vire uma barra sem sentido na tela.
NAO_JANELA = ("credits", "spend_limit", "plan_type", "limit_id", "limit_name")

PASTA = "limits"
ARQUIVO_CLAUDE = "claude.json"


@dataclass(frozen=True)
class Janela:
    """Uma janela de limite: quanto já foi usado e quando ela zera."""

    usado: float  # percentual, preso em [0, 100]
    minutos: int  # tamanho da janela
    zera_em: float | None = None  # epoch em segundos, ou None se implausível

    @property
    def curta(self) -> bool:
        return self.minutos <= CURTA_MAX_MINUTOS

    @property
    def label(self) -> str:
        """`5h` · `7d` — o tamanho da janela do jeito que se lê."""
        if self.minutos % (24 * 60) == 0:
            return f"{self.minutos // (24 * 60)}d"
        if self.minutos % 60 == 0:
            return f"{self.minutos // 60}h"
        return f"{self.minutos}m"

    def falta(self, agora: float) -> float | None:
        """Segundos até zerar, ou None se não há carimbo confiável."""
        if self.zera_em is None:
            return None
        return max(0.0, self.zera_em - agora)

    def vencida(self, agora: float) -> bool:
        """A janela já virou desde que este número foi medido.

        Acontece toda vez: você usou o codex ontem, a janela de 5 h dele zerou
        de madrugada e o rollout continua guardando os 18% de antes. O número
        existe, mas **não vale mais** — e é o próprio `resets_at` que diz isso.
        A mesma armadilha pegou o Claude Code, que a corrigiu na 2.1.251
        ("status line rate_limits ... still showing a rate-limit window's
        pre-reset usage percentage after the window reset while the session was
        idle"). Aqui a resposta é não mostrar percentual: quem venceu aparece
        com um traço, e a barra fica vazia.
        """
        return self.zera_em is not None and self.zera_em <= agora


@dataclass(frozen=True)
class Consumo:
    """O que sabemos do limite de um agente, e de quando sabemos."""

    kind: str  # "codex" | "claude"
    curta: Janela | None = None
    longa: Janela | None = None
    medido: float | None = None  # quando o agente escreveu o dado (epoch)
    plano: str = ""

    @property
    def janelas(self) -> list[Janela]:
        return [j for j in (self.curta, self.longa) if j is not None]

    def idade(self, agora: float) -> float | None:
        """Há quanto tempo este número foi medido. `None` se nem isso sabemos."""
        if self.medido is None:
            return None
        return max(0.0, agora - self.medido)


def _numero(bruto, campos) -> float | None:
    for campo in campos:
        valor = bruto.get(campo)
        if isinstance(valor, bool):
            continue  # `True` é 1 em Python, e não é um percentual
        if isinstance(valor, (int, float)):
            return float(valor)
        if isinstance(valor, str):
            try:
                return float(valor)
            except ValueError:
                continue
    return None


def _epoch_plausivel(valor) -> float | None:
    """Epoch em segundos, se o carimbo for de um tempo que existe.

    Milissegundos são aceitos (e convertidos) porque agente nenhum promete a
    unidade. `0`, `-1` e ano 3000 viram `None`: contador que conta para trás,
    ou para daqui a mil anos, é pior que contador nenhum.
    """
    if isinstance(valor, str):
        valor = _epoch(valor)
        if valor is None:
            return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    segundos = float(valor)
    if segundos > 1e11:  # carimbo em milissegundos
        segundos /= 1000
    if not EPOCH_MIN <= segundos <= EPOCH_MAX:
        return None
    return segundos


def _janela(bruto, minutos_supostos: int | None = None) -> Janela | None:
    """Uma janela a partir do bloco do agente, ou `None` se não der para crer.

    Validação de faixa, e não de conteúdo: percentual preso em [0, 100], janela
    positiva e de tamanho plausível, carimbo de reset num tempo que existe. O
    reset ruim não invalida a janela — perde-se o "zera em", não a barra.
    """
    if not isinstance(bruto, dict):
        return None
    usado = _numero(bruto, CAMPOS_USADO)
    minutos = _numero(bruto, CAMPOS_MINUTOS)
    if minutos is None and minutos_supostos is not None:
        minutos = float(minutos_supostos)
    if usado is None or not 0.0 <= usado <= 100.0:
        return None
    if minutos is None or not 1 <= minutos <= JANELA_MAX_MINUTOS:
        return None
    zera = None
    for campo in CAMPOS_RESET:
        zera = _epoch_plausivel(bruto.get(campo))
        if zera is not None:
            break
    return Janela(usado=usado, minutos=int(minutos), zera_em=zera)


def consumo(kind: str, bruto, medido: float | None = None) -> Consumo | None:
    """Normaliza o `rate_limits` de qualquer um dos dois agentes.

    A classificação é pelo **tamanho** da janela, não pelo nome do campo: é o
    que sobrevive ao Claude Code batizar de outra forma o bloco que o codex
    chama de `primary`. O nome entra só quando o bloco não se mede — e nada é
    inventado: bloco sem percentual ou sem tamanho nenhum fica de fora.
    """
    if not isinstance(bruto, dict):
        return None
    curta: Janela | None = None
    longa: Janela | None = None
    for nome, valor in bruto.items():
        if not isinstance(nome, str) or nome in NAO_JANELA:
            continue
        janela = _janela(valor, MINUTOS_POR_NOME.get(nome.lower()))
        if janela is None:
            continue
        if janela.curta and curta is None:
            curta = janela
        elif not janela.curta and longa is None:
            longa = janela
    if curta is None and longa is None:
        return None
    plano = bruto.get("plan_type")
    return Consumo(
        kind=kind,
        curta=curta,
        longa=longa,
        medido=medido,
        plano=plano if isinstance(plano, str) else "",
    )


class LeitorCodex:
    """O último `token_count` de um rollout — o dado está lá, de graça."""

    kind = "codex"

    def __init__(self, home: Path) -> None:
        self.raiz = home / ".codex" / "sessions"

    def ler(self) -> Consumo | None:
        if not self.raiz.is_dir():
            return None
        try:
            candidatos = _por_mtime(self.raiz.glob("*/*/*/rollout-*.jsonl"), ARQUIVOS_VISTOS)
        except OSError:
            return None
        for caminho in candidatos:
            achado = self._do_arquivo(caminho)
            if achado is not None:
                return achado
        return None

    def _do_arquivo(self, caminho: Path) -> Consumo | None:
        for entrada in reversed(_tail(caminho)):
            payload = entrada.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "token_count":
                continue
            achado = consumo(self.kind, payload.get("rate_limits"), _epoch(entrada.get("timestamp")))
            if achado is not None:
                return achado
        return None


class LeitorClaude:
    """O que o `watchai --statusline` gravou — o Claude Code empurra, nós lemos.

    Sem a statusline configurada não há arquivo, e não há barra do Claude. É
    assim de propósito: o app funciona inteiro sem, e inventar o número seria
    pior que não ter.
    """

    kind = "claude"

    def __init__(self, pasta: Path) -> None:
        self.arquivo = pasta / ARQUIVO_CLAUDE

    def ler(self) -> Consumo | None:
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(dados, dict):
            return None
        return consumo(self.kind, dados.get("rate_limits"), _epoch_plausivel(dados.get("medido")))


class Limites:
    """Os limites dos agentes, relidos de tempos em tempos.

    O cache existe porque a varredura de processos roda a cada 2 s e abrir
    rollouts a cada volta seria pagar disco por um número que muda de hora em
    hora. `agora` é argumento para o teste não depender de relógio.
    """

    def __init__(self, home: Path | None = None, pasta: Path | None = None, leitores=None) -> None:
        casa = home or Path.home()
        destino = pasta if pasta is not None else limits_dir()
        self.leitores = list(leitores) if leitores is not None else [
            LeitorCodex(casa),
            LeitorClaude(destino),
        ]
        self._cache: list[Consumo] = []
        self._lido: float | None = None

    def ler(self, agora: float) -> list[Consumo]:
        """O consumo de cada agente que tem número. Lista vazia é resposta boa."""
        if self._lido is not None and agora - self._lido < INTERVALO:
            return self._cache
        self._lido = agora
        achados = []
        for leitor in self.leitores:
            try:
                achado = leitor.ler()
            except Exception:
                achado = None  # leitor quebrado apaga a barra dele, não o app
            if achado is not None:
                achados.append(achado)
        self._cache = achados
        return achados

    def invalidar(self) -> None:
        """Força a próxima leitura a ir ao disco — é o que o `R` faz."""
        self._lido = None


def limits_dir() -> Path:
    """Onde a statusline deixa o recado. Fica junto da config do usuário."""
    from .. import config

    return config.config_dir() / PASTA


def gravar(dados: dict, pasta: Path | None = None, arquivo: str = ARQUIVO_CLAUDE) -> bool:
    """Grava o recado da statusline de forma atômica. True se conseguiu.

    Atômica porque a statusline roda **a cada render** do agente, e mais de uma
    sessão pode estar rodando: sem tmp + rename o WatchAI leria um arquivo pela
    metade. O tmp leva o pid no nome para duas sessões não disputarem o mesmo.
    """
    destino = (pasta if pasta is not None else limits_dir()) / arquivo
    temporario = destino.with_suffix(f".{os.getpid()}.tmp")
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario.write_text(json.dumps(dados, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporario, destino)
    except OSError:
        try:
            temporario.unlink()
        except OSError:
            pass
        return False
    return True


def _atalho_casa(caminho: str) -> str:
    try:
        casa = str(Path.home())
    except (OSError, RuntimeError):
        return caminho
    if caminho == casa:
        return "~"
    return "~" + caminho[len(casa) :] if caminho.startswith(casa + os.sep) else caminho


def statusline(texto: str, pasta: Path | None = None, agora: float | None = None) -> str:
    """O modo `watchai --statusline`: recebe o JSON do agente, guarda o limite
    e devolve a linha que ele vai mostrar.

    Roda dentro do Claude Code, a cada render, então **não levanta nunca** e não
    demora: JSON quebrado, disco cheio ou campo novo viram linha vazia — o
    agente mostra nada, que é melhor que mostrar erro no lugar do prompt.
    """
    try:
        return _statusline(texto, pasta, agora if agora is not None else time.time())
    except Exception:
        return ""


def _statusline(texto: str, pasta: Path | None, agora: float) -> str:
    try:
        dados = json.loads(texto)
    except ValueError:
        return ""
    if not isinstance(dados, dict):
        return ""

    limites = dados.get("rate_limits")
    if isinstance(limites, dict):
        gravar(
            {"kind": "claude", "medido": agora, "source": "statusline", "rate_limits": limites},
            pasta,
        )

    partes = []
    espaco = dados.get("workspace") if isinstance(dados.get("workspace"), dict) else {}
    pasta_atual = espaco.get("current_dir") or dados.get("cwd")
    if isinstance(pasta_atual, str) and pasta_atual:
        partes.append(_atalho_casa(pasta_atual))
    modelo = dados.get("model") if isinstance(dados.get("model"), dict) else {}
    nome = modelo.get("display_name") or modelo.get("id")
    if isinstance(nome, str) and nome:
        partes.append(nome)
    achado = consumo("claude", limites, agora)
    if achado is not None:
        partes += [f"{j.label} {j.usado:.0f}%" for j in achado.janelas]
    custo = dados.get("cost") if isinstance(dados.get("cost"), dict) else {}
    total = custo.get("total_cost_usd")
    if isinstance(total, (int, float)) and not isinstance(total, bool) and total > 0:
        partes.append(f"${total:.2f}")
    return " · ".join(partes)


__all__ = [
    "APERTA",
    "ARQUIVO_CLAUDE",
    "Consumo",
    "ESTOURANDO",
    "IDADE_VISIVEL",
    "INTERVALO",
    "Janela",
    "LeitorClaude",
    "LeitorCodex",
    "Limites",
    "consumo",
    "gravar",
    "limits_dir",
    "statusline",
]
