"""O que cada agente está fazendo — lido do diário que ele mesmo grava.

Claude Code e Codex escrevem um `.jsonl` por sessão no seu disco. Ler esse
arquivo **não é integração**: não há API, hook, credencial nem configuração do
agente envolvida — é o mesmo que olhar um log.

É daqui que sai a distinção que o processo sozinho não dá:

* última entrada é texto do assistente **que fechou o turno** → **READY**
  (terminou, é a sua vez);
* é um erro de API (limite de sessão, token expirado) → **ERROR**;
* é uma chamada de ferramenta sem resposta → ferramenta pendente: **WORKING**
  se o processo está gastando CPU, **INPUT** se está parado (ou seja, travado
  esperando você confirmar);
* é o resultado de uma ferramenta, um bloco de raciocínio, um texto de
  passagem ou uma mensagem sua → **WORKING** (a rodada continua em aberto).

O "que fechou o turno" é o ponto inteiro. O Claude Code grava **um bloco por
linha**, e o texto de passagem ("vou olhar o arquivo X") sai igualzinho ao texto
final da resposta. Quem separa os dois é o `stop_reason`, que vem em toda
entrada: sem olhar para ele, sete em cada oito textos de uma sessão real viram
"terminou", e o verde pisca a cada ferramenta que o agente chama.

Nada aqui pode levantar: arquivo ausente, corrompido ou em formato novo vira
`None`, e o provider cai nos sinais de processo.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

# Quanto lemos do fim do arquivo. Uma entrada de transcript raramente passa de
# alguns KB; 64 KB cobrem várias com folga.
CAUDA_BYTES = 64 * 1024

# "Pensando" há mais de dois minutos sem nada novo no arquivo não é pensar: é
# um diário parado. Aí o processo decide.
FRESCOR_SEGUNDOS = 120.0

# O diretório nem sempre está na cauda: o codex só o grava no `session_meta` e
# nos `turn_context`, e numa sessão longa o último fica a megabytes do fim. Vale
# procurar mais fundo — uma vez por arquivo, e guardando o resultado.
CAUDA_FUNDA = 8 * 1024 * 1024

# Quantas linhas do começo do arquivo dizem de quem ele é. O Claude Code hoje
# abre o diário com quatro linhas de metadados sem carimbo e sem diretório: o
# `cwd` e a hora da primeira mensagem só aparecem na quinta.
CABECALHO_LINHAS = 40

# Agente sem diário costuma ser coisa de instante: a sessão acabou de abrir e
# ainda não escreveu a primeira linha. Procurar de novo a cada volta para
# sempre, porém, é varrer o disco a cada dois segundos — a pasta de rollouts do
# codex junta milhares de arquivos. Insistimos nas primeiras voltas e, depois,
# de tempos em tempos.
TENTATIVAS_SEGUIDAS = 8
ESPACO_TENTATIVAS = 30

# Estados que o diário sabe dizer.
FEITO = "done"
PENSANDO = "thinking"
FERRAMENTA = "tool_pending"
ERRO = "error"

# `stop_reason` que diz "esta mensagem não é o fim do turno": o modelo parou
# para chamar uma ferramenta e volta na entrada seguinte. Qualquer outro motivo
# — `end_turn`, `stop_sequence`, `max_tokens`, ou motivo nenhum, que é o que
# formato antigo e mensagem interrompida gravam — encerra a rodada.
TURNO_ABERTO = ("tool_use", "pause_turn")

# Entradas `user` que não são você falando: o eco de um comando de barra, a
# saída de um `!comando`, o aviso de interrupção. O Claude Code se anota no
# diário pela mesma porta por onde passam as suas mensagens, e nenhuma dessas
# anotações começa uma rodada.
ENCANAMENTO = (
    "<command-name>",
    "<command-message>",
    "<command-args>",
    "<local-command-stdout>",
    "<local-command-caveat>",
    "<bash-input>",
    "<bash-stdout>",
    "<bash-stderr>",
    "[Request interrupted",
)


@dataclass(frozen=True)
class Leitura:
    estado: str  # FEITO | PENSANDO | FERRAMENTA | ERRO
    atividade: str
    mtime: float
    desde: float | None = None  # quando o estado começou, segundo o diário
    # Onde o agente está trabalhando **agora**. O cwd do processo é onde ele
    # começou: quem abre o agente na home e depois entra no projeto mantém o
    # processo na home para sempre. O diário grava o diretório a cada mensagem.
    cwd: str = ""

    def fresca(self, agora: float) -> bool:
        return agora - self.mtime <= FRESCOR_SEGUNDOS


def _resumo(texto, limite: int = 50) -> str:
    """A primeira frase de um erro, curta o bastante para caber no card.

    Mensagem de limite de uso vem com link e data de retorno junto; o que
    interessa na linha do card é a primeira frase.
    """
    limpo = " ".join(str(texto).split())
    return limpo.split(". ")[0].rstrip(".")[:limite] or "error"


def _caminho(valor: str) -> str:
    """O diretório como caminho de sistema.

    O codex grava `file:///...` em boa parte dos eventos, e `Path("file:///x")`
    não é o caminho `/x` — é uma pasta chamada `file:`.
    """
    if not valor.startswith("file://"):
        return valor
    caminho = unquote(urlparse(valor).path)
    # `file:///C:/Users/voce` vira `/C:/Users/voce`: no Windows a barra sobra.
    if len(caminho) > 2 and caminho[0] == "/" and caminho[2] == ":":
        caminho = caminho[1:]
    return caminho or valor


def _cwd_em(objeto, profundidade: int = 6) -> str:
    """Qualquer `cwd` dentro da entrada, em qualquer nível.

    O codex grava o diretório em lugares diferentes conforme o evento: no
    `payload` do `turn_context` e dentro de `payload.item` nos eventos de item.
    Procurar em dois níveis fixos achava só o primeiro — e o primeiro é o
    diretório em que a sessão **abriu**, não o de agora.
    """
    if profundidade < 0:
        return ""
    if isinstance(objeto, dict):
        valor = objeto.get("cwd")
        if isinstance(valor, str) and valor:
            return _caminho(valor)
        filhos = objeto.values()
    elif isinstance(objeto, list):
        filhos = objeto
    else:
        return ""
    for filho in filhos:
        achado = _cwd_em(filho, profundidade - 1)
        if achado:
            return achado
    return ""


def _cwd_do_arquivo(caminho: Path, limite: int = CAUDA_FUNDA) -> str:
    """O último diretório gravado no diário, procurando de trás para frente.

    Só as linhas que mencionam o campo são decodificadas: um diário de 20 MB
    tem dezenas de milhares de entradas, e aqui interessa exatamente uma.
    """
    try:
        with caminho.open("rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - limite))
            bruto = f.read()
    except OSError:
        return ""
    for linha in reversed(bruto.split(b"\n")):
        if b'"cwd"' not in linha:
            continue
        try:
            entrada = json.loads(linha)
        except ValueError:
            continue
        achado = _cwd_em(entrada)
        if achado:
            return achado
    return ""


@dataclass(frozen=True)
class Cabecalho:
    """A identidade de um diário: onde a sessão abriu e quando ela começou.

    O começo é o que desempata duas sessões abertas na mesma pasta — ver
    `Transcripts.atribuir`.
    """

    cwd: str = ""
    inicio: float | None = None


# O começo de um diário não muda: ele só cresce. Guardar o que já foi lido
# evita reabrir dezenas de arquivos a cada volta — a busca do codex olha os
# quarenta rollouts mais recentes para achar o do diretório certo.
_CABECALHOS: dict[Path, tuple[tuple[float, int], Cabecalho]] = {}


def _cabecalho(caminho: Path, limite: int = CABECALHO_LINHAS) -> Cabecalho:
    """O diretório e o instante da primeira mensagem, lidos do começo.

    Antes isto era `_primeira_linha(p).get("cwd")`, e o formato novo do Claude
    Code passou a abrir o arquivo com metadados (`mode`, `permission-mode`…)
    que não têm campo nenhum: a busca por diretório casava com arquivo nenhum e
    a reserva do casamento por `cwd` virou código morto.
    """
    try:
        st = caminho.stat()
    except OSError:
        return Cabecalho()
    marca = (st.st_mtime, st.st_size)
    guardado = _CABECALHOS.get(caminho)
    if guardado is not None and guardado[0] == marca:
        return guardado[1]

    cwd, inicio = "", None
    try:
        with caminho.open("r", encoding="utf-8", errors="replace") as f:
            for _, linha in zip(range(limite), f):
                try:
                    entrada = json.loads(linha)
                except ValueError:
                    continue
                if not isinstance(entrada, dict):
                    continue
                if not cwd:
                    cwd = _cwd_em(entrada)
                if inicio is None:
                    inicio = _epoch(entrada.get("timestamp"))
                if cwd and inicio is not None:
                    break
    except OSError:
        return Cabecalho()
    achado = Cabecalho(cwd, inicio)
    _CABECALHOS[caminho] = (marca, achado)
    return achado


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


def slug(cwd: str) -> str:
    """O nome da pasta que o Claude Code dá ao projeto: o caminho com os
    separadores virados em `-`.

    O `:` entra na conta por causa do Windows — `C:\\Users\\voce` sem essa troca
    não é sequer um nome de pasta válido lá.
    """
    return "-" + cwd.strip("/\\").replace("/", "-").replace("\\", "-").replace(":", "-")


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


def _fim_de_turno(entrada: dict) -> bool:
    """A mensagem fechou o turno, ou continua na entrada seguinte?

    É o `stop_reason` que sabe — o texto de passagem e o texto de entrega são
    gravados do mesmo jeito, no mesmo tipo de bloco, e nada mais os distingue.
    """
    return ((entrada.get("message") or {}).get("stop_reason")) not in TURNO_ABERTO


def _entrega(entrada: dict, quando: float | None) -> tuple[str, str, float | None]:
    """O que um texto do assistente significa: entrega ou parada no caminho."""
    if _fim_de_turno(entrada):
        return (FEITO, "task completed", quando)
    return (PENSANDO, "thinking", quando)


def _e_pedido(entrada: dict, texto: str) -> bool:
    """A entrada `user` é você falando?"""
    return not entrada.get("isMeta") and not texto.lstrip().startswith(ENCANAMENTO)


class Diario:
    """O que todo leitor de diário faz igual: achar os candidatos e dizer ao
    cache quando vale reler."""

    def arquivos(self, cwd: str) -> list[Path]:
        """Os diários que podem ser deste diretório, do mais recente ao mais
        antigo. Plural porque duas sessões abertas na mesma pasta são dois."""
        raise NotImplementedError

    def chave(self, caminho: Path) -> float:
        """O que faz a leitura mudar, para o cache saber quando reler.

        O mtime do arquivo, em geral. O Claude Code é a exceção: enquanto um
        sub-agente trabalha, quem cresce é o diário **dele**, e o do principal
        fica parado — ver `ClaudeCode.chave`.
        """
        return caminho.stat().st_mtime


class ClaudeCode(Diario):
    """`~/.claude/projects/<slug>/<sessão>.jsonl`.

    Ao lado, `<slug>/<sessão>/subagents/agent-*.jsonl`: um diário por
    sub-agente disparado pela ferramenta `Agent`.
    """

    kind = "claude"

    # Quantos diários de sub-agente vale a pena abrir. Uma sessão longa junta
    # dezenas ao longo do dia; os que dizem algo são os que mudaram por último.
    SUBAGENTES_MAX = 20

    def __init__(self, home: Path) -> None:
        self.raiz = home / ".claude" / "projects"
        self._vivos: dict[Path, tuple[float, bool]] = {}  # sub-agente -> rodada aberta?

    def arquivos(self, cwd: str) -> list[Path]:
        if not self.raiz.is_dir():
            return []
        # Tentamos o slug e, se não houver, procuramos pelo `cwd` que o próprio
        # arquivo grava.
        direto = self.raiz / slug(cwd)
        if direto.is_dir():
            candidatos = sorted(
                direto.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if candidatos:
                return candidatos
        todos = sorted(
            self.raiz.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:40]
        return [p for p in todos if _cabecalho(p).cwd == cwd]

    @staticmethod
    def _pasta_subagentes(caminho: Path) -> Path:
        """`<sessão>.jsonl` -> `<sessão>/subagents/`."""
        return caminho.parent / caminho.stem / "subagents"

    def chave(self, caminho: Path) -> float:
        """O mtime mais novo entre o diário e os dos sub-agentes dele.

        Sem os sub-agentes na conta, o cache congelava: o diário do principal
        não é escrito enquanto eles trabalham, então a leitura guardada valia
        para sempre e o trabalho deles nunca aparecia.
        """
        mtime = caminho.stat().st_mtime
        pasta = self._pasta_subagentes(caminho)
        if not pasta.is_dir():
            return mtime
        return max([mtime, *(p.stat().st_mtime for p in pasta.glob("*.jsonl"))])

    def _subagentes(self, caminho: Path) -> tuple[int, float]:
        """Quantos sub-agentes ainda têm rodada aberta, e quando escreveram.

        A ferramenta `Agent` é assíncrona: ela responde "launched" em um
        décimo de segundo, o turno do principal fecha em seguida com um
        `end_turn` — e o diário dele não volta a crescer até os sub-agentes
        terminarem. Lido só o diário do principal, a sessão ficava verde,
        "pode vir buscar", com quatro agentes no meio do trabalho.
        """
        pasta = self._pasta_subagentes(caminho)
        if not pasta.is_dir():
            return 0, 0.0
        recentes = sorted(
            pasta.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
        )[: self.SUBAGENTES_MAX]
        vivos, mtime = 0, 0.0
        for arquivo in recentes:
            aberto, quando = self._aberto(arquivo)
            if not aberto:
                continue
            vivos += 1
            mtime = max(mtime, quando)
        return vivos, mtime

    def _aberto(self, arquivo: Path) -> tuple[bool, float]:
        """(este sub-agente ainda tem rodada aberta, quando ele escreveu).

        Guardado por arquivo: quem entregou não escreve mais nada, e reler os
        diários dos que já acabaram a cada volta era o custo de uma sessão que
        dispara muitos de uma vez.
        """
        try:
            mtime = arquivo.stat().st_mtime
        except OSError:
            return False, 0.0
        lembrado = self._vivos.get(arquivo)
        if lembrado is not None and lembrado[0] == mtime:
            return lembrado[1], mtime
        leitura = self._leitura(arquivo)
        aberto = leitura is not None and leitura.estado != FEITO
        self._vivos[arquivo] = (mtime, aberto)
        return aberto, mtime

    def ler(self, caminho: Path) -> Leitura | None:
        leitura = self._leitura(caminho)
        if leitura is not None and leitura.estado in (ERRO, FERRAMENTA):
            # Erro e ferramenta pendente são do principal e mandam: ele parou.
            return leitura
        vivos, mtime = self._subagentes(caminho)
        if not vivos:
            return leitura
        atividade = f"{vivos} subagents" if vivos > 1 else "1 subagent"
        # O mtime é o do sub-agente, não o do principal: é o relógio dele que
        # diz se isto ainda está acontecendo. Uma corrida interrompida deixa os
        # diários parados, e aí o card cai em WAITING — amarelo, sem alarme —
        # em vez de anunciar um "terminou" que ninguém entregou.
        return Leitura(
            PENSANDO,
            atividade,
            mtime,
            leitura.desde if leitura else None,
            leitura.cwd if leitura else _cabecalho(caminho).cwd,
        )

    def _leitura(self, caminho: Path) -> Leitura | None:
        entradas = _tail(caminho)
        if not entradas:
            return None
        mtime = caminho.stat().st_mtime
        pendentes: dict[str, tuple[str, str, float | None]] = {}  # id -> (nome, detalhe, quando)
        ultimo = None  # (estado, atividade, quando)
        cwd = ""
        for entrada in entradas:
            if isinstance(entrada.get("cwd"), str) and entrada["cwd"]:
                cwd = _caminho(entrada["cwd"])
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
                # Sua mensagem entra no diário como texto solto. Ela é o começo
                # da rodada, não o fim: a resposta só é gravada quando o
                # primeiro bloco dela fecha, e esse silêncio — mediana de 19 s,
                # nove em cada dez abaixo de 72 s — era lido como "terminou".
                # O verde acendia justo no instante em que o agente pegava o
                # trabalho, e apagava quando ele chamava a primeira ferramenta.
                if tipo == "assistant":
                    ultimo = _entrega(entrada, quando)
                elif _e_pedido(entrada, conteudo):
                    ultimo = (PENSANDO, "thinking", quando)
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
                elif kind == "thinking":
                    # Raciocínio é prova de rodada em aberto: ninguém pensa
                    # depois de entregar.
                    ultimo = (PENSANDO, "thinking", quando)
                elif kind == "text" and tipo == "assistant":
                    ultimo = _entrega(entrada, quando)
                elif kind == "text" and _e_pedido(entrada, _texto(conteudo)):
                    # Sua mensagem, com anexo junto: mesma coisa que a de cima,
                    # só que gravada em bloco em vez de texto solto.
                    ultimo = (PENSANDO, "thinking", quando)
        if pendentes:
            ferramenta, detalhe, quando = next(reversed(list(pendentes.values())))
            texto = f"{ferramenta}: {detalhe}" if detalhe else ferramenta
            return Leitura(FERRAMENTA, texto, mtime, quando, cwd)
        if ultimo is None:
            return None
        return Leitura(ultimo[0], ultimo[1], mtime, ultimo[2], cwd)


class Codex(Diario):
    """`~/.codex/sessions/AAAA/MM/DD/rollout-*.jsonl` — traz eventos explícitos."""

    kind = "codex"

    EVENTOS = {
        "task_complete": (FEITO, "task completed"),
        "task_started": (PENSANDO, "thinking"),
        "error": (ERRO, "error"),
        "stream_error": (ERRO, "stream error"),
    }
    APROVACAO = ("approval_request", "exec_approval", "patch_approval")
    # A ferramenta já respondeu e o modelo voltou a pensar. Sem reconhecer a
    # saída, a varredura de trás para frente passava por ela, achava a chamada
    # e deixava o card em "esperando" com o agente trabalhando.
    SAIDAS = ("function_call_output", "custom_tool_call_output", "local_shell_call_output")

    def __init__(self, home: Path) -> None:
        self.raiz = home / ".codex" / "sessions"

    def arquivos(self, cwd: str) -> list[Path]:
        if not self.raiz.is_dir():
            return []
        recentes = sorted(
            self.raiz.glob("*/*/*/rollout-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:40]
        return [p for p in recentes if _cabecalho(p).cwd == cwd]

    def ler(self, caminho: Path) -> Leitura | None:
        entradas = _tail(caminho)
        if not entradas:
            return None
        mtime = caminho.stat().st_mtime
        cwd = ""
        for entrada in entradas:
            achado = _cwd_em(entrada)
            if achado:
                cwd = achado
        for entrada in reversed(entradas):
            payload = entrada.get("payload") or {}
            tipo = payload.get("type") or ""
            quando = _epoch(entrada.get("timestamp"))
            if any(a in tipo for a in self.APROVACAO):
                return Leitura(FERRAMENTA, "waiting for approval", mtime, quando, cwd)
            if tipo in self.EVENTOS:
                estado, atividade = self.EVENTOS[tipo]
                # `task_complete` não quer dizer que deu certo: quando bate o
                # limite de uso, o codex fecha a rodada com o erro **dentro** do
                # evento (`last_agent_message: null`). Ler só o tipo pintava de
                # verde uma sessão que parou e não volta sozinha.
                erro = payload.get("error")
                if isinstance(erro, dict) and erro.get("message"):
                    return Leitura(ERRO, _resumo(erro["message"]), mtime, quando, cwd)
                return Leitura(estado, atividade, mtime, quando, cwd)
            if tipo in self.SAIDAS:
                return Leitura(PENSANDO, "thinking", mtime, quando, cwd)
            if tipo in ("function_call", "local_shell_call", "custom_tool_call"):
                detalhe = _detalhe(payload.get("arguments") if isinstance(payload.get("arguments"), dict) else None)
                nome = payload.get("name") or "tool"
                return Leitura(FERRAMENTA, f"{nome}: {detalhe}" if detalhe else nome, mtime, quando, cwd)
        return None


class OpenCode(Diario):
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

    def arquivos(self, cwd: str) -> list[Path]:
        pasta = self._info()
        if not pasta.is_dir():
            return []
        candidatos = sorted(pasta.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        # O campo do diretório já se chamou "directory" e "cwd"; aceitamos os
        # dois para não quebrar na próxima versão.
        return [
            caminho
            for caminho in candidatos[:40]
            if (dados := _primeira_linha(caminho) or {}).get("directory") == cwd
            or dados.get("cwd") == cwd
        ]

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
        self._candidatos: dict[tuple[str, str], list[Path]] = {}
        self._faltas: dict[tuple[str, str], int] = {}  # voltas sem diário para todos
        self._cache: dict[Path, tuple[float, Leitura | None]] = {}
        self._cwd: dict[Path, str] = {}  # diretório por arquivo, achado uma vez

    def atribuir(
        self, kind: str, cwd: str | None, agentes: list[tuple[int, float]]
    ) -> dict[int, Leitura | None]:
        """Qual diário é de qual agente. `agentes` é `[(pid, nascimento)]`.

        Casar só por diretório não distingue duas sessões abertas na mesma
        pasta — e duas sessões na mesma pasta é o caso comum de quem abre uma
        aba para o código e outra para os testes. As duas caíam no arquivo de
        mtime mais alto, e o card de uma passava a mostrar a atividade da
        outra: o pior tipo de erro num monitor, porque parece informação.

        Aqui cada diário vai para um agente só. O desempate é o relógio: uma
        sessão grava a primeira mensagem segundos depois de o processo nascer,
        enquanto a distância até o diário da sessão vizinha é de minutos. Quem
        sobra sem diário cai nos sinais de processo — menos informação, mas
        informação certa.
        """
        leitor = self.leitores.get(kind)
        if leitor is None or not cwd:
            return {pid: None for pid, _ in agentes}
        try:
            escolha = self._parear(agentes, self._opcoes(leitor, kind, cwd, len(agentes)))
            return {
                pid: (self._do_arquivo(leitor, caminho) if caminho else None)
                for pid, caminho in escolha.items()
            }
        except OSError:
            return {pid: None for pid, _ in agentes}

    def _opcoes(self, leitor, kind: str, cwd: str, quantos: int) -> list[Path]:
        """Os diários possíveis deste diretório, guardados entre voltas.

        Reprocurar a cada ciclo custa uma varredura de disco por sessão. A
        lista é refeita quando algum arquivo sumiu — e, quando falta diário
        para alguém, nas tentativas espaçadas de `_insistir`: é assim que uma
        sessão recém-aberta entra, sem transformar a falta permanente (uma
        pasta onde nunca houve diário) em varredura eterna.
        """
        chave = (kind, cwd)
        guardados = self._candidatos.get(chave)
        if guardados is None or any(not c.exists() for c in guardados):
            return self._procurar(leitor, chave, cwd, quantos)
        if len(guardados) < quantos and self._insistir(chave):
            return self._procurar(leitor, chave, cwd, quantos)
        return guardados

    def _procurar(self, leitor, chave: tuple[str, str], cwd: str, quantos: int) -> list[Path]:
        """Varre o disco atrás dos diários e zera a contagem **se achou para
        todos**: zerar em toda procura fazia `_insistir` ver sempre a primeira
        tentativa, e o espaçamento não espaçava nada."""
        achados = leitor.arquivos(cwd)
        self._candidatos[chave] = achados
        if len(achados) >= quantos:
            self._faltas.pop(chave, None)
        return achados

    def _insistir(self, chave: tuple[str, str]) -> bool:
        """Vale varrer o disco de novo atrás do diário que falta?"""
        voltas = self._faltas.get(chave, 0) + 1
        self._faltas[chave] = voltas
        return voltas <= TENTATIVAS_SEGUIDAS or voltas % ESPACO_TENTATIVAS == 0

    def _parear(
        self, agentes: list[tuple[int, float]], candidatos: list[Path]
    ) -> dict[int, Path | None]:
        """O emparelhamento propriamente dito: um diário por agente."""
        if not candidatos:
            return {pid: None for pid, _ in agentes}
        if len(agentes) == 1:
            return {agentes[0][0]: candidatos[0]}

        distancias = sorted(
            (abs(comeco - nascimento), pid, caminho)
            for pid, nascimento in agentes
            for caminho in candidatos
            if (comeco := _cabecalho(caminho).inicio) is not None
        )
        escolha: dict[int, Path | None] = {}
        usados: set[Path] = set()
        for _, pid, caminho in distancias:
            if pid in escolha or caminho in usados:
                continue
            escolha[pid] = caminho
            usados.add(caminho)

        # Diário sem carimbo de hora (formato antigo, arquivo truncado) não
        # entra no desempate: sobra para quem ainda não tem, na ordem de mtime.
        sobrando = [c for c in candidatos if c not in usados]
        for pid, _ in sorted(agentes, key=lambda a: a[1], reverse=True):
            if pid in escolha:
                continue
            escolha[pid] = sobrando.pop(0) if sobrando else None
        return escolha

    def _do_arquivo(self, leitor, caminho: Path) -> Leitura | None:
        """A leitura de um arquivo, relida só quando ele muda."""
        chave = leitor.chave(caminho)
        anterior = self._cache.get(caminho)
        if anterior is not None and anterior[0] == chave:
            return anterior[1]  # nada mudou: não relê o arquivo
        leitura = self._com_diretorio(caminho, leitor.ler(caminho))
        self._cache[caminho] = (chave, leitura)
        return leitura

    def _com_diretorio(self, caminho: Path, leitura: Leitura | None) -> Leitura | None:
        """Garante o diretório de trabalho na leitura.

        O Claude Code carimba o diretório em toda entrada; o codex, só de vez em
        quando. Quando a cauda não traz nada, vale a varredura funda — uma vez
        por arquivo, guardada depois: trocar de pasta é raro, reler megabytes a
        cada volta não é.
        """
        if leitura is None:
            return None
        if leitura.cwd:
            self._cwd[caminho] = leitura.cwd
            return leitura
        lembrado = self._cwd.get(caminho)
        if lembrado is None:
            lembrado = _cwd_do_arquivo(caminho)
            self._cwd[caminho] = lembrado
        return replace(leitura, cwd=lembrado) if lembrado else leitura

    def esquecer(self, kind: str, cwd: str) -> None:
        self._candidatos.pop((kind, cwd), None)
        self._faltas.pop((kind, cwd), None)


__all__ = [
    "CABECALHO_LINHAS",
    "Cabecalho",
    "Diario",
    "ENCANAMENTO",
    "ERRO",
    "FEITO",
    "FERRAMENTA",
    "FRESCOR_SEGUNDOS",
    "Leitura",
    "ESPACO_TENTATIVAS",
    "PENSANDO",
    "TENTATIVAS_SEGUIDAS",
    "TURNO_ABERTO",
    "Transcripts",
]
