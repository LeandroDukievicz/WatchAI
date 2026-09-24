"""Detecção real: transforma a tabela de processos em terminais e agentes.

O card é o **terminal**; os agentes rodando nele viram `Session.agents`. Nada
aqui fala com IA nenhuma: só lê processos.

A classe é partida em duas metades de propósito:

* `read()` faz só I/O (varredura de processos, ~50 ms) e roda numa thread;
* `apply()` mexe no store e roda na thread da UI.

Sem essa separação a varredura engasgaria a animação a cada ciclo.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..models import AVISO_FECHADO, REMOCAO_FECHADO, Session, SessionStore, Status, agregar
from .source import ProcObs, ProcessSource, PsutilSource, Snapshot
from .transcript import ERRO, FEITO, FERRAMENTA, PENSANDO, Leitura, Transcripts

# Quanto de CPU (segundos por segundo de relógio) separa "trabalhando" de
# "parado". Um agente ocioso fica em zero mesmo com a TUI dele aberta.
CPU_OCUPADO = 0.05

STARTING_SEGUNDOS = 4.0

# Ferramenta pendente com o processo parado: se o diário também está parado há
# mais que isto, quem está esperando é você (pedido de confirmação); se acabou
# de escrever, o agente está esperando um processo externo.
ESPERA_HUMANA = 8.0

# Com o turno já fechado, quanto tempo de CPU seguida desfaz o "terminou".
# Um pico não é trabalho: a TUI do agente redesenha, o contador de espera do
# limite de uso pisca, o processo arruma a casa. Sem esta confirmação o card
# alternava entre READY e WORKING a cada varredura — zerando o contador e
# enchendo o EVENT STREAM de linhas que não eram notícia nenhuma.
CONFIRMA_TRABALHO = 5.0
AVISO_SEGUNDOS = AVISO_FECHADO.total_seconds()  # o card avisa que vai sair
REMOCAO_SEGUNDOS = REMOCAO_FECHADO.total_seconds()  # e sai dois minutos depois

ATIVIDADE = {
    Status.WORKING: "working",
    Status.READY: "idle",
    Status.STARTING: "starting",
    Status.OFFLINE: "session ended",
}


def _projeto(cwd: str | None) -> str:
    """Nome curto do projeto. A home vira `~`: ali o nome da pasta é o seu
    nome de usuário, que não diz nada sobre o que a sessão faz."""
    if not cwd:
        return ""
    caminho = Path(cwd)
    if caminho == Path.home():
        return "~"
    return caminho.name or cwd


def _encurtar(caminho: str | None) -> str:
    """O caminho como você o escreveria: `~`, `~/Projetos/WatchAI`.

    A home inteira vira `~` — `relative_to` devolve `.` ali, e `~/.` não é
    como ninguém escreve o próprio diretório. As barras saem no formato posix
    para o título ficar igual nos três sistemas.
    """
    if not caminho:
        return ""
    try:
        relativo = Path(caminho).relative_to(Path.home())
    except ValueError:
        return caminho
    return "~" if str(relativo) == "." else "~/" + relativo.as_posix()


# Quantos segmentos do caminho cabem no título do card sem virar sopa de
# letrinhas. `~/Projetos/WatchAI` passa inteiro; um caminho de mount fundo vira
# `…/CIENTISTA DE DADOS/Videos`, que é justamente o pedaço que identifica.
SEGMENTOS_TITULO = 3


def _titulo(caminho: str) -> str:
    """O caminho encolhido para caber na borda do card, cortado pela esquerda:
    num caminho, o que diz de que projeto se trata está no fim."""
    partes = [parte for parte in caminho.split("/") if parte]
    if len(partes) <= SEGMENTOS_TITULO:
        return caminho
    return "…/" + "/".join(partes[-(SEGMENTOS_TITULO - 1):])


class LiveProvider:
    """Mantém o `SessionStore` igual ao que existe na máquina."""

    def __init__(
        self,
        store: SessionStore,
        source: ProcessSource | None = None,
        *,
        transcripts: Transcripts | None = None,
        aviso: float = AVISO_SEGUNDOS,
        remocao: float = REMOCAO_SEGUNDOS,
    ) -> None:
        self.store = store
        self.source = source or PsutilSource()
        self.transcripts = Transcripts() if transcripts is None else transcripts
        self.aviso = aviso
        self.remocao = remocao
        # pid -> (cpu da árvore, cpu do próprio agente, epoch)
        self._cpu: dict[int, tuple[float, float, float]] = {}
        self._ocupado_desde: dict[int, float] = {}  # pid -> início da CPU seguida
        self._leituras: dict[int, Leitura | None] = {}  # pid -> diário, por varredura
        self._proximo_id = 1
        # Por que a última leitura veio vazia — é o que a tela mostra no lugar
        # de "nenhuma sessão" quando o problema não é ausência de sessão.
        self.diagnostico = ""
        # A primeira leitura é um inventário do que já estava aberto: ela não
        # deve encher o EVENT STREAM com um "agente iniciou" por sessão antiga.
        self._inventario = True

    # -- I/O (thread) ----------------------------------------------------------
    def read(self) -> Snapshot:
        return self.source.snapshot()

    def poll(self, now: datetime) -> bool:
        return self.apply(self.read(), now)

    # -- reconciliação (thread da UI) -----------------------------------------
    def apply(self, snap: Snapshot, now: datetime) -> bool:
        agora = now.timestamp()
        self.diagnostico = snap.diagnostico
        mudou = False
        raizes = self._raizes(snap.agents)
        self._leituras = self._diarios(raizes)
        grupos: dict[str, list[ProcObs]] = {}
        for o in raizes:
            grupos.setdefault(o.terminal, []).append(o)

        for key, grupo in grupos.items():
            grupo.sort(key=lambda o: o.created)
            sessao = self._sessao(key)
            if sessao is None:
                sessao = self._abrir(key, grupo, snap, now)
                mudou = True
            elif sessao.closed_at is not None:
                # A tty foi reaproveitada por um terminal novo: é outra sessão.
                self._reabrir(sessao, grupo, snap, now)
                mudou = True
            mudou |= self._atualizar(sessao, grupo, agora, now)

        for sessao in list(self.store.sessions):
            if sessao.key in grupos or not sessao.key:
                continue
            mudou |= self._sem_agentes(sessao, now)

        # Processos que sumiram não precisam mais de histórico de CPU.
        vivos = {o.pid for o in snap.agents}
        for pid in [p for p in self._cpu if p not in vivos]:
            del self._cpu[pid]
            self._ocupado_desde.pop(pid, None)
        self._inventario = False
        return mudou

    # -- desduplicação ---------------------------------------------------------
    @staticmethod
    def _raizes(agents) -> list[ProcObs]:
        """Um agente por árvore.

        O `codex` aparece como três processos (shim do node → binário → host de
        ferramentas) e é **um** agente. Fica quem não tem ancestral do mesmo
        tipo na lista.
        """
        por_pid = {o.pid: o for o in agents}
        return [
            o
            for o in agents
            if not any(
                (pai := por_pid.get(a)) is not None and pai.kind == o.kind
                for a in o.ancestors
            )
        ]

    def _diarios(self, agentes: list[ProcObs]) -> dict[int, Leitura | None]:
        """O diário de cada agente, resolvido de uma vez só.

        De uma vez só porque a escolha é coletiva: duas sessões abertas na
        mesma pasta disputam os mesmos arquivos, e quem decide de quem é cada
        um precisa ver as duas juntas. Perguntando de uma em uma, as duas
        recebiam o mesmo diário — e um card mostrava a atividade do outro.
        """
        if self.transcripts is None:
            return {}
        por_pasta: dict[tuple[str, str], list[tuple[int, float]]] = {}
        for o in agentes:
            if o.cwd:
                por_pasta.setdefault((o.kind, o.cwd), []).append((o.pid, o.created))
        leituras: dict[int, Leitura | None] = {}
        for (kind, cwd), grupo in por_pasta.items():
            leituras.update(self.transcripts.atribuir(kind, cwd, grupo))
        return leituras

    # -- sessões ---------------------------------------------------------------
    def _sessao(self, key: str) -> Session | None:
        return next((s for s in self.store.sessions if s.key == key), None)

    def _cwd(self, grupo: list[ProcObs]) -> str | None:
        """Onde o agente está trabalhando — segundo ele, não segundo o processo.

        O cwd do processo é onde a sessão **começou**: quem abre o agente na
        home e depois entra no projeto mantém o processo na home para sempre, e
        o card ficava com o nome da tty (`PTS/7`) porque a home não tem projeto
        legível. O diário grava o diretório a cada mensagem, e é esse que diz em
        que projeto a sessão está agora.
        """
        for o in grupo:
            leitura = self._leituras.get(o.pid)
            if leitura is not None and leitura.cwd:
                return leitura.cwd
        return next((o.cwd for o in grupo if o.cwd), None)

    def _rotulos(self, grupo: list[ProcObs]) -> tuple[str, str, str, str]:
        """(título do card, nome curto, projeto, diretório).

        O título é o **caminho onde a aba está aberta** — `~`,
        `~/Projetos/WatchAI`. Vale para toda aba, inclusive a que está na home,
        onde antes sobrava o rótulo da tty (`PTS/9`) e você não fazia ideia de
        qual sessão era.

        O curto é outra coisa, e por isso não é o mesmo texto: ele vai para a
        coluna de oito casas do EVENT STREAM e para o modo compacto, onde um
        caminho cortado não diria nada e o nome do projeto diz.
        """
        cwd = self._cwd(grupo)
        projeto = _projeto(cwd)
        rotulo = grupo[0].terminal_label
        curto = rotulo.upper() if projeto in ("", "~") else projeto.upper()
        caminho = _encurtar(cwd)
        return (_titulo(caminho) if caminho else rotulo.upper()), curto, projeto, cwd or ""

    def _abrir(self, key: str, grupo: list[ProcObs], snap: Snapshot, now: datetime) -> Session:
        nome, curto, projeto, cwd = self._rotulos(grupo)
        term = snap.terminals.get(key)
        inicio = datetime.fromtimestamp(
            term.started if term else grupo[0].terminal_started
        )
        sessao = Session(
            id=self._proximo_id,
            name=nome,
            short=curto,
            status=Status.STARTING,
            project=projeto,
            directory=_encurtar(cwd),
            pid=grupo[0].pid,
            started_at=inicio,
            status_since=now,
            activity=ATIVIDADE[Status.STARTING],
            key=key,
            terminal=term.label if term else grupo[0].terminal_label,
            tty=key if key.startswith("/dev/") else "",
            window_pid=grupo[0].window_pid,
            window_app=grupo[0].window_app,
        )
        self._proximo_id += 1
        self.store.sessions.append(sessao)
        # No inventário da abertura cada terminal rende só a linha do estado
        # real (que sai da agregação). "terminal detectado" é notícia quando
        # uma aba nova aparece com o app já rodando.
        if not self._inventario:
            self.store.log(sessao, now, "terminal detected")
        return sessao

    def _reabrir(self, sessao: Session, grupo: list[ProcObs], snap: Snapshot, now: datetime) -> None:
        nome, curto, projeto, cwd = self._rotulos(grupo)
        term = snap.terminals.get(sessao.key)
        sessao.name, sessao.short = nome, curto
        sessao.project = projeto
        sessao.directory = _encurtar(cwd)
        sessao.started_at = datetime.fromtimestamp(
            term.started if term else grupo[0].terminal_started
        )
        sessao.closed_at = None
        sessao.window_pid = grupo[0].window_pid
        sessao.window_app = grupo[0].window_app
        sessao.agents.clear()
        self.store.log(sessao, now, "terminal detected")

    @staticmethod
    def _instante(desde: float | None, agora: float, now: datetime) -> datetime:
        """Quando o estado começou. O diário sabe a hora de verdade; sem ele,
        vale agora — que é quando **nós** vimos.

        Carimbo no futuro (relógio torto, fuso mal gravado) vira agora: um
        contador negativo na tela é pior que um contador otimista.
        """
        if desde is None or desde > agora:
            return now
        return datetime.fromtimestamp(desde)

    def _atualizar(
        self, sessao: Session, grupo: list[ProcObs], agora: float, now: datetime
    ) -> bool:
        mudou = False
        por_pid = {a.pid: a for a in sessao.agents}
        novos = []
        for o in grupo:
            status, atividade, desde = self._estado(o, agora)
            comecou = self._instante(desde, agora, now)
            agente = por_pid.pop(o.pid, None)
            if agente is None:
                from ..models import Agent

                agente = Agent(
                    pid=o.pid,
                    kind=o.kind,
                    label=o.label,
                    status=status,
                    activity=atividade,
                    started_at=datetime.fromtimestamp(o.created),
                    status_since=comecou,
                )
                if not self._inventario:
                    self.store.log(sessao, now, f"{o.label} started")
                mudou = True
            elif agente.status is not status:
                agente.status, agente.status_since = status, comecou
                agente.activity = atividade
                mudou = True
            else:
                agente.activity = atividade
            novos.append(agente)

        for sumido in por_pid.values():  # agentes que saíram
            self.store.log(sessao, now, f"{sumido.label} exited")
            mudou = True

        sessao.agents = novos
        # O rótulo é relido a cada volta: o agente que entra num projeto depois
        # de abrir troca de diretório sem trocar de processo, e o card tem que
        # acompanhar — é a diferença entre `PTS/7` e `WATCHAI` na tela.
        nome, curto, projeto, cwd = self._rotulos(grupo)
        if (nome, curto) != (sessao.name, sessao.short):
            sessao.name, sessao.short = nome, curto
            mudou = True
        sessao.project, sessao.directory = projeto, _encurtar(cwd)
        return self._agregar(sessao, now) or mudou

    def _sem_agentes(self, sessao: Session, now: datetime) -> bool:
        """Sem agente rodando, a sessão acabou — e começa a contagem para sair.

        Vale igual para a aba fechada e para o agente encerrado com a aba ainda
        aberta: o que o card monitora é a **sessão de IA**, não o terminal. Uma
        aba que você deixou aberta depois de sair do agente não é notícia, e
        ficar na tela para sempre só ocupa espaço de quem está rodando.
        """
        if sessao.closed_at is None:
            sessao.agents = []
            sessao.closed_at = now
            self.store.transition(sessao, Status.OFFLINE, ATIVIDADE[Status.OFFLINE], now)
            return True

        fechado = (now - sessao.closed_at).total_seconds()
        if fechado >= self.remocao:
            self.store.sessions.remove(sessao)
            return True
        return False

    def _agregar(self, sessao: Session, now: datetime) -> bool:
        status = agregar(a.status for a in sessao.agents)
        # A atividade do card é a do agente que decidiu o estado — com mais de
        # um agente, o nome dele vem junto para não ficar ambígua.
        dono = next((a for a in sessao.agents if a.status is status), None)
        atividade = (
            f"{dono.label}: {dono.activity}"
            if dono and len(sessao.agents) > 1
            else (dono.activity if dono else ATIVIDADE[Status.OFFLINE])
        )
        if status is sessao.status and atividade == sessao.activity:
            return False
        self.store.transition(sessao, status, atividade, now)
        # O contador do card é o do agente que decidiu o estado: se o diário
        # sabe desde quando, é esse tempo que vale — não o instante em que o
        # WatchAI abriu.
        if dono is not None:
            sessao.status_since = dono.status_since
        return True

    # -- estado de um agente ---------------------------------------------------
    def _cpu_ativa(self, o: ProcObs, agora: float) -> tuple[bool, bool]:
        """(a árvore gastou CPU, o próprio agente gastou CPU) desde a volta
        anterior.

        Os dois números existem porque medem coisas diferentes. A árvore
        inclui o que a sessão abriu e não fechou — um navegador, um servidor de
        desenvolvimento —, e esse consumo é trabalho enquanto o diário disser
        que há rodada aberta; com o turno fechado ele é só um programa ligado,
        e contá-lo deixava a sessão eternamente "trabalhando".

        Chamar isto mais de uma vez por varredura estraga a medição: é aqui que
        o histórico é atualizado.
        """
        anterior = self._cpu.get(o.pid)
        self._cpu[o.pid] = (o.cpu, o.cpu_proprio, agora)
        if anterior is None:
            return False, False
        passou = agora - anterior[2]
        if passou <= 0:
            return False, False
        return (
            (o.cpu - anterior[0]) / passou > CPU_OCUPADO,
            (o.cpu_proprio - anterior[1]) / passou > CPU_OCUPADO,
        )

    def _seguido(self, pid: int, ativo: bool, agora: float) -> float | None:
        """Desde quando este processo está ocupado sem interrupção, ou None."""
        if not ativo:
            self._ocupado_desde.pop(pid, None)
            return None
        return self._ocupado_desde.setdefault(pid, agora)

    def _estado(self, o: ProcObs, agora: float) -> tuple[Status, str, float | None]:
        """O estado de um agente, e desde quando.

        O diário diz o quê, o processo diz se anda.

        Nenhum dos dois sozinho resolve — o processo não sabe distinguir
        "terminou" de "travou esperando você", e o diário não sabe se o que ele
        registrou por último ainda está acontecendo.
        """
        arvore, proprio = self._cpu_ativa(o, agora)
        ocupado = arvore or bool(o.tool_children)
        desde_ocupado = self._seguido(o.pid, proprio, agora)
        if agora - o.created < STARTING_SEGUNDOS:
            return Status.STARTING, ATIVIDADE[Status.STARTING], o.created

        leitura = self._leituras.get(o.pid)
        if leitura is not None:
            desde = leitura.desde
            if leitura.estado == ERRO:
                return Status.ERROR, leitura.atividade, desde
            if leitura.estado == FERRAMENTA:
                if ocupado:
                    return Status.WORKING, leitura.atividade, desde
                # Parado com ferramenta pendente: o diário mudo há mais de
                # ESPERA_HUMANA é pedido de confirmação; recém-escrito é espera
                # por algo externo.
                parado = agora - leitura.mtime
                if parado >= ESPERA_HUMANA:
                    return Status.INPUT, leitura.atividade, desde
                return Status.WAITING, leitura.atividade, desde
            if leitura.estado == PENSANDO:
                if ocupado or leitura.fresca(agora):
                    return Status.WORKING, leitura.atividade, desde
                # Diário parado no meio da rodada: o agente recebeu o resultado
                # da ferramenta e ainda não escreveu a resposta. Isso **não** é
                # "terminou" — um turno que acaba deixa texto no diário, e é
                # esse texto que vira FEITO. O diário envelhece porque só é
                # escrito quando a mensagem fecha: um pensamento longo passa dos
                # dois minutos sem gastar CPU nenhuma (a espera é do outro lado
                # da rede). Chamar isso de READY acendia o verde e ainda apitava
                # "pode vir buscar" com o agente no meio do trabalho.
                return Status.WAITING, leitura.atividade, desde
            if leitura.estado == FEITO:
                # Turno fechado: o diário é a palavra final, e um pico de CPU
                # não a desfaz. O que desfaz é CPU **do agente**, seguida: é
                # assim que aparece a resposta que ele já começou a gerar e
                # ainda não gravou — os ~19 s de silêncio entre a sua mensagem
                # e a primeira linha dela no arquivo.
                if desde_ocupado is not None and agora - desde_ocupado >= CONFIRMA_TRABALHO:
                    atividade = (
                        f"running {o.tool_label}" if o.tool_label else ATIVIDADE[Status.WORKING]
                    )
                    return Status.WORKING, atividade, desde_ocupado
                return Status.READY, leitura.atividade, desde

        if ocupado:
            # Sem diário, a ferramenta que está rodando é a melhor resposta
            # para "o que ele está fazendo" — e funciona com qualquer agente.
            return (
                Status.WORKING,
                f"running {o.tool_label}" if o.tool_label else ATIVIDADE[Status.WORKING],
                None,
            )
        return Status.READY, ATIVIDADE[Status.READY], None

    # -- consulta para a UI ----------------------------------------------------
    def expirando(self, sessao: Session, now: datetime) -> bool:
        """True quando o card já passou do aviso e vai sumir em instantes."""
        fechado = sessao.closed_for(now)
        return fechado is not None and fechado.total_seconds() >= self.aviso


__all__ = [
    "AVISO_SEGUNDOS",
    "CPU_OCUPADO",
    "LiveProvider",
    "REMOCAO_SEGUNDOS",
    "STARTING_SEGUNDOS",
]
