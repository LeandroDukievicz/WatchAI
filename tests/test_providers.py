"""Detecção real: reconhecimento de agente, agrupamento por terminal e estados.

Nada aqui olha a máquina de quem roda: a tabela de processos é injetada e o
relógio é um argumento. Os transcripts são arquivos de mentira num `tmp_path`.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from watchai.models import AVISO_FECHADO, REMOCAO_FECHADO, SessionStore, Status
from watchai.providers import LiveProvider, ProcObs, Snapshot, TermObs, identify
from watchai.providers.transcript import Transcripts

AGORA = datetime(2026, 9, 21, 22, 0, 0)


def obs(pid, kind="claude", terminal="/dev/pts/1", cwd="/home/eu/proj", **kw):
    padroes = dict(
        label=kind,
        terminal_label=terminal.replace("/dev/", ""),
        terminal_started=(AGORA - timedelta(hours=2)).timestamp(),
        created=(AGORA - timedelta(hours=1)).timestamp(),
        cpu=10.0,
        cwd=cwd,
        tool_children=0,
        ancestors=(),
        window_pid=None,
        window_app="",
    )
    padroes.update(kw)
    return ProcObs(pid=pid, kind=kind, terminal=terminal, **padroes)


def snap(*agentes, terminais=None):
    terms = {
        o.terminal: TermObs(o.terminal, o.terminal_label, o.terminal_started) for o in agentes
    }
    for t in terminais or ():
        terms.setdefault(t, TermObs(t, t.replace("/dev/", ""), AGORA.timestamp()))
    return Snapshot(agents=tuple(agentes), terminals=terms)


class Fonte:
    def __init__(self, s=None):
        self.s = s or Snapshot()

    def snapshot(self):
        return self.s


def provider(store=None, fonte=None, transcripts=None):
    return LiveProvider(store or SessionStore(), fonte or Fonte(), transcripts=transcripts or None)


# ---- quem é agente ---------------------------------------------------------


def test_reconhece_o_programa_e_ignora_o_caminho_parecido():
    assert identify(["claude", "--dangerously-skip-permissions"]).key == "claude"
    assert identify(["/usr/local/bin/codex", "--yolo"]).key == "codex"
    assert identify(["node", "/home/eu/.nvm/versions/node/v24/bin/gemini"]).key == "gemini"
    # Windows: o processo é node.exe e o nome do agente só existe no caminho
    assert identify(
        ["node.exe", r"C:\Users\eu\AppData\npm\@anthropic-ai\claude-code\cli.js"]
    ).key == "claude"
    # o Antigravity CLI se chama `agy`, e é binário nativo: o nome é tudo o que há
    assert identify(["agy"]).key == "antigravity"
    assert identify(["/home/eu/.local/bin/agy"]).key == "antigravity"
    # o plugin do Telegram tem "claude" no caminho e NÃO é agente
    assert identify(["bun", "run", "--cwd", "/home/eu/.claude/plugins/telegram", "start"]) is None
    assert identify(["nvim", "claude.md"]) is None
    assert identify([]) is None
    assert identify(None) is None


# ---- terminais e agentes ---------------------------------------------------


def test_um_card_por_terminal_com_os_agentes_dentro():
    store = SessionStore()
    p = provider(store, Fonte(snap(
        obs(10, "claude", "/dev/pts/1"),
        obs(11, "codex", "/dev/pts/1"),
        obs(20, "claude", "/dev/pts/2", cwd="/home/eu/outro"),
    )))
    p.poll(AGORA)
    assert [s.terminal for s in store.sessions] == ["pts/1", "pts/2"]
    primeiro = store.sessions[0]
    assert [a.label for a in primeiro.agents] == ["claude", "codex"]
    # O título é o caminho da aba; o nome curto (EVENT STREAM) é o projeto.
    assert primeiro.name == "/home/eu/proj"
    assert primeiro.short == "PROJ"
    assert store.sessions[1].name == "/home/eu/outro"


def test_arvore_do_mesmo_agente_conta_uma_vez():
    """O codex aparece como shim do node -> binário -> host. É um agente só."""
    store = SessionStore()
    p = provider(store, Fonte(snap(
        obs(100, "codex", ancestors=()),
        obs(101, "codex", ancestors=(100,)),
        obs(102, "codex", ancestors=(101, 100)),
    )))
    p.poll(AGORA)
    assert len(store.sessions) == 1
    assert [a.pid for a in store.sessions[0].agents] == [100]


def test_estado_do_card_e_o_do_agente_que_mais_pede_voce():
    store = SessionStore()
    fonte = Fonte(snap(
        obs(10, "claude", cpu=10.0),
        obs(11, "codex", cpu=10.0),
    ))
    p = provider(store, fonte)
    p.poll(AGORA)
    # segunda leitura: o codex gastou CPU (trabalhando), o claude não (pronto)
    fonte.s = snap(obs(10, "claude", cpu=10.0), obs(11, "codex", cpu=12.0))
    p.poll(AGORA + timedelta(seconds=2))
    estados = {a.label: a.status for a in store.sessions[0].agents}
    assert estados == {"claude": Status.READY, "codex": Status.WORKING}
    assert store.sessions[0].status is Status.READY  # "terminou" ganha de "trabalhando"
    assert store.sessions[0].activity.startswith("claude:")  # e diz de quem é


# ---- ciclo de vida do terminal ---------------------------------------------


def test_agente_encerrado_comeca_a_contagem_para_sair():
    """Mesmo com a aba aberta: o que o card monitora é a sessão de IA, não o
    terminal. Sem agente, ela acabou — e o card tem prazo, senão uma aba
    esquecida ocupa a tela para sempre."""
    store = SessionStore()
    fonte = Fonte(snap(obs(10)))
    p = provider(store, fonte)
    p.poll(AGORA)
    fonte.s = snap(terminais=["/dev/pts/1"])  # agente saiu, aba continua aberta
    p.poll(AGORA + timedelta(seconds=5))
    sessao = store.sessions[0]
    assert sessao.status is Status.OFFLINE
    assert sessao.agents == [] and sessao.closed_at is not None
    # e some no mesmo prazo de uma aba fechada
    p.poll(AGORA + REMOCAO_FECHADO + timedelta(minutes=1))
    assert store.sessions == []


def test_terminal_fechado_avisa_por_dois_minutos_e_some():
    store = SessionStore()
    fonte = Fonte(snap(obs(10)))
    p = provider(store, fonte)
    p.poll(AGORA)
    fonte.s = Snapshot()  # a aba sumiu
    p.poll(AGORA + timedelta(seconds=1))
    sessao = store.sessions[0]
    assert sessao.status is Status.OFFLINE and sessao.closed_at is not None
    # antes dos 5 min: fica quieto
    assert sessao.closing_in(AGORA + timedelta(minutes=4)) is None
    # depois: avisa quanto falta
    falta = sessao.closing_in(AGORA + AVISO_FECHADO + timedelta(seconds=1))
    assert falta is not None and falta <= REMOCAO_FECHADO - AVISO_FECHADO
    # e aos 7 min sai da tela
    p.poll(AGORA + REMOCAO_FECHADO + timedelta(seconds=1))
    assert store.sessions == []


def test_tty_reaproveitada_vira_sessao_nova():
    store = SessionStore()
    fonte = Fonte(snap(obs(10, cwd="/home/eu/antigo")))
    p = provider(store, fonte)
    p.poll(AGORA)
    fonte.s = Snapshot()
    p.poll(AGORA + timedelta(seconds=1))
    fonte.s = snap(obs(99, cwd="/home/eu/novo"))  # outro terminal, mesma tty
    p.poll(AGORA + timedelta(minutes=1))
    assert len(store.sessions) == 1
    assert store.sessions[0].project == "novo"
    assert store.sessions[0].closed_at is None


# ---- o que o agente está fazendo (transcript) ------------------------------


def escreve_transcript(
    home: Path, cwd: str, entradas: list[dict], nome: str = "sessao.jsonl"
) -> Path:
    # A mesma regra do produto, importada de lá: quando o helper tinha a dele,
    # um caminho do Windows (`C:\\Users\\voce`) virava nome de pasta inválido.
    from watchai.providers.transcript import slug

    pasta = home / ".claude" / "projects" / slug(cwd)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / nome
    arquivo.write_text("\n".join(json.dumps(e) for e in entradas) + "\n", encoding="utf-8")
    return arquivo


def carimbo(quando: datetime) -> str:
    """A hora como o diário grava: ISO-8601 em UTC, terminado em Z."""
    texto = quando.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    return texto.replace("+00:00", "Z")


def abertura(quando: datetime) -> dict:
    """A primeira mensagem da sessão — é o carimbo dela que diz quando ela
    começou, e é isso que desempata dois diários na mesma pasta."""
    return {"type": "user", "message": {"content": "oi"}, "timestamp": carimbo(quando)}


def assistente(*blocos, parou="end_turn"):
    """Uma entrada do assistente. `parou` é o `stop_reason` da mensagem:
    `tool_use` é passagem (o turno continua), `end_turn` é entrega."""
    return {"type": "assistant", "message": {"content": list(blocos), "stop_reason": parou}}


def voce(texto, **kw):
    return {"type": "user", "message": {"content": texto}, **kw}


def test_transcript_diz_que_terminou(tmp_path):
    escreve_transcript(tmp_path, "/home/eu/proj", [assistente({"type": "text", "text": "pronto"})])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(AGORA)
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.READY and agente.activity == "task completed"


def test_ferramenta_pendente_com_processo_parado_e_voce_que_ele_espera(tmp_path):
    """É a distinção que o PID sozinho não dá: READY x INPUT."""
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "tool_use", "id": "t1", "name": "Bash",
                    "input": {"command": "rm -rf build"}}),
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    # o arquivo acabou de ser escrito; passados 30 s sem nada novo, é você
    p.poll(datetime.now() + timedelta(seconds=30))
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.INPUT
    assert agente.activity == "Bash: rm -rf build"


def test_mesma_ferramenta_com_o_processo_ocupado_e_trabalho(tmp_path):
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "tool_use", "id": "t1", "name": "Bash",
                    "input": {"command": "npm test"}}),
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, tool_children=1))), Transcripts(tmp_path))
    p.poll(datetime.now() + timedelta(seconds=30))
    assert store.sessions[0].agents[0].status is Status.WORKING


def test_resultado_de_ferramenta_e_trabalho(tmp_path):
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "a.py"}}),
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}},
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(datetime.now())
    assert store.sessions[0].agents[0].status is Status.WORKING


def test_pensar_por_muito_tempo_nao_e_ter_terminado(tmp_path):
    """O diário só é escrito quando a mensagem fecha, e um pensamento longo
    passa dos dois minutos sem gastar CPU — a espera é do outro lado da rede.
    Tratar isso como "terminou" acendia o verde e apitava "pode vir buscar" com
    o agente no meio da rodada."""
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "a.py"}}),
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}},
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    # bem depois do FRESCOR, e com o processo parado: continua sendo uma rodada
    # em aberto, não uma tarefa entregue.
    p.poll(datetime.now() + timedelta(seconds=600))
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.WAITING
    assert agente.status.slot != "green"


def test_texto_no_meio_da_rodada_nao_acende_o_verde(tmp_path):
    """A causa do semáforo piscando: o Claude Code grava **um bloco por linha**,
    e o "vou olhar o arquivo X" que vem antes de uma ferramenta é gravado
    igualzinho ao texto final. Só o `stop_reason` separa os dois — sem ele, cada
    ferramenta chamada rendia um verde de alguns segundos."""
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "text", "text": "vou olhar o arquivo"}, parou="tool_use"),
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(datetime.now())
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.WORKING
    assert agente.status.slot != "green"


def test_texto_que_fecha_o_turno_acende_o_verde(tmp_path):
    """E o mesmo bloco, com o turno fechado, é a entrega: aí sim é a sua vez."""
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "text", "text": "vou olhar o arquivo"}, parou="tool_use"),
        assistente({"type": "text", "text": "pronto, era isso"}, parou="end_turn"),
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(datetime.now())
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.READY and agente.status.slot == "green"


def test_sua_mensagem_comeca_a_rodada_em_vez_de_terminar(tmp_path):
    """O diário só volta a ser escrito quando o primeiro bloco da resposta
    fecha — mediana de 19 s numa sessão real, nove em cada dez abaixo de 72 s.
    Esse silêncio era lido como "terminou", e o verde acendia justamente no
    instante em que o agente pegava o trabalho."""
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "text", "text": "pronto"}, parou="end_turn"),
        voce("agora arruma o build"),
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(datetime.now())
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.WORKING
    assert agente.status.slot != "green"


def test_raciocinio_e_rodada_em_aberto(tmp_path):
    """Ninguém pensa depois de entregar."""
    escreve_transcript(tmp_path, "/home/eu/proj", [
        voce("arruma o build"),
        assistente({"type": "thinking", "thinking": "..."}, parou="tool_use"),
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(datetime.now())
    assert store.sessions[0].agents[0].status is Status.WORKING


def test_comando_local_nao_tira_o_verde_de_quem_ja_entregou(tmp_path):
    """O Claude Code se anota no diário pela mesma porta das suas mensagens: o
    eco de um `/comando` e a saída de um `!comando` entram como `user`. Tratar
    isso como rodada nova deixaria em "trabalhando" uma sessão parada."""
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "text", "text": "pronto"}, parou="end_turn"),
        voce("<local-command-caveat>Caveat: ...</local-command-caveat>", isMeta=True),
        voce("<command-name>/clear</command-name>"),
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(datetime.now())
    assert store.sessions[0].agents[0].status is Status.READY


def escreve_rollout_codex(home: Path, cwd: str, entradas: list[dict]) -> Path:
    pasta = home / ".codex" / "sessions" / "2026" / "09" / "22"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "rollout-2026-09-22T13-45-41-teste.jsonl"
    cabeca = {"type": "session_meta", "payload": {"type": "session_meta", "cwd": cwd}}
    linhas = [cabeca, *entradas]
    arquivo.write_text("\n".join(json.dumps(e) for e in linhas) + "\n", encoding="utf-8")
    return arquivo


def test_limite_de_uso_do_codex_e_erro_e_nao_tarefa_concluida(tmp_path):
    """O codex fecha a rodada com `task_complete` mesmo quando bateu o limite —
    o motivo vem dentro, em `error`, com `last_agent_message: null`. Ler só o
    tipo do evento pintava de verde uma sessão que parou e não volta sozinha."""
    escreve_rollout_codex(tmp_path, "/home/eu/proj", [
        {"timestamp": "2026-09-22T22:03:51.070Z", "type": "event_msg", "payload": {
            "type": "task_complete",
            "last_agent_message": None,
            "error": {"message": "You\u2019ve hit your usage limit. Upgrade to Pro "
                                 "(https://exemplo), try again at Sep 27th, 2026."},
        }},
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, "codex"))), Transcripts(tmp_path))
    p.poll(datetime.now())
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.ERROR
    assert agente.status.slot == "red"
    # só a primeira frase: o link e a data de retorno não cabem na linha do card
    assert agente.activity == "You\u2019ve hit your usage limit"


def test_codex_que_terminou_bem_continua_sendo_tarefa_concluida(tmp_path):
    escreve_rollout_codex(tmp_path, "/home/eu/proj", [
        {"timestamp": "2026-09-22T22:03:51.070Z", "type": "event_msg", "payload": {
            "type": "task_complete", "last_agent_message": "pronto",
        }},
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, "codex"))), Transcripts(tmp_path))
    p.poll(datetime.now())
    assert store.sessions[0].agents[0].status is Status.READY


def test_saida_da_ferramenta_do_codex_e_trabalho_e_nao_espera(tmp_path):
    """A varredura de trás para frente não conhecia o evento de saída: passava
    por ele, achava a chamada e deixava o card em "esperando você" com o agente
    já de volta ao trabalho."""
    escreve_rollout_codex(tmp_path, "/home/eu/proj", [
        {"timestamp": "2026-09-22T22:03:50.000Z", "type": "response_item", "payload": {
            "type": "custom_tool_call", "name": "shell",
            "arguments": {"command": "pytest"},
        }},
        {"timestamp": "2026-09-22T22:03:50.370Z", "type": "response_item", "payload": {
            "type": "custom_tool_call_output", "output": "ok",
        }},
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, "codex"))), Transcripts(tmp_path))
    p.poll(datetime.now() + timedelta(seconds=30))
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.WORKING


def test_o_titulo_do_card_e_o_caminho_da_aba():
    """Toda aba passa a ser identificada do mesmo jeito: pelo caminho em que
    está aberta. Antes, a que não tinha projeto legível virava `PTS/9`, que não
    diz nada sobre de qual sessão se trata."""
    from watchai.providers.live import _encurtar, _titulo

    casa = str(Path.home())
    assert _encurtar(casa) == "~"  # e não "~/.", que ninguém escreve
    assert _encurtar(str(Path.home() / "Projetos" / "WatchAI")) == "~/Projetos/WatchAI"
    assert _encurtar(None) == ""

    # Cabendo, o caminho vai inteiro.
    assert _titulo("~") == "~"
    assert _titulo("~/Projetos/WatchAI") == "~/Projetos/WatchAI"
    assert _titulo("/usr/local") == "/usr/local"
    # Fundo demais, corta pela esquerda: o que identifica o projeto está no fim.
    assert _titulo("/run/media/disco/EBAC/CIENTISTA DE DADOS/Videos") == "…/CIENTISTA DE DADOS/Videos"
    assert _titulo("~/Projetos/a/b/c") == "…/b/c"


def test_o_projeto_do_card_vem_do_diario_e_nao_do_processo(tmp_path):
    """Quem abre o agente na home e depois entra no projeto mantém o **processo**
    na home para sempre. Como a home não tem nome de projeto legível (ali a
    pasta se chama como você), o card caía no rótulo da tty — `PTS/7` no lugar
    do projeto. O diário grava o diretório a cada mensagem."""
    casa = str(Path.home())
    entrada = assistente({"type": "text", "text": "pronto"})
    entrada["cwd"] = str(Path.home() / "Projetos" / "WatchAI")
    escreve_transcript(tmp_path, casa, [entrada])

    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, cwd=casa))), Transcripts(tmp_path))
    p.poll(AGORA)
    assert store.sessions[0].name == "~/Projetos/WatchAI"
    assert store.sessions[0].short == "WATCHAI"
    assert store.sessions[0].project == "WatchAI"

    # E o contraste: sem diário, a home não diz projeto nenhum e sobra a tty.
    # (O diário vai para uma pasta vazia de propósito: `transcripts=None` faria
    # o provider ler o diário real de quem está rodando o teste.)
    sem = SessionStore()
    provider(sem, Fonte(snap(obs(10, cwd=casa))), Transcripts(tmp_path / "vazio")).poll(AGORA)
    assert sem.sessions[0].name == "~"  # a aba está na home, e o título diz isso
    assert sem.sessions[0].short == "PTS/1"  # sem projeto, o curto é o terminal


def test_o_card_acompanha_o_agente_que_troca_de_projeto(tmp_path):
    """Trocar de pasta não troca o processo: o rótulo é relido a cada volta."""
    casa = str(Path.home())
    primeira = assistente({"type": "text", "text": "pronto"})
    primeira["cwd"] = str(Path.home() / "Projetos" / "WatchAI")
    escreve_transcript(tmp_path, casa, [primeira])

    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, cwd=casa))), Transcripts(tmp_path))
    p.poll(AGORA)
    assert store.sessions[0].name == "~/Projetos/WatchAI"

    segunda = assistente({"type": "text", "text": "pronto"})
    segunda["cwd"] = str(Path.home() / "Projetos" / "DerivaSocial")
    escreve_transcript(tmp_path, casa, [segunda])
    p.transcripts.esquecer("claude", casa)
    p.poll(AGORA + timedelta(seconds=3))
    assert store.sessions[0].name == "~/Projetos/DerivaSocial"


def test_caminho_entende_o_file_uri():
    """O codex grava o diretório como URI em boa parte dos eventos, e
    `Path("file:///x")` não é o caminho `/x` — é uma pasta chamada `file:`."""
    from watchai.providers.transcript import _caminho

    assert _caminho("/home/eu/proj") == "/home/eu/proj"
    assert _caminho("file:///home/eu/proj") == "/home/eu/proj"
    assert _caminho("file:///home/eu/um%20espaco") == "/home/eu/um espaco"
    assert _caminho("file:///C:/Users/eu") == "C:/Users/eu"  # a barra da frente sai


def test_o_projeto_do_codex_vem_de_fundo_no_diario(tmp_path):
    """O codex grava o diretório só de vez em quando, e aninhado em
    `payload.item`. Numa sessão longa o último fica muito antes do fim, fora da
    cauda de 64 KB — e o card ficava com o nome da tty."""
    casa = str(Path.home())
    projeto = Path.home() / "Projetos" / "WatchAI"
    enchimento = [
        {"timestamp": "2026-09-22T22:00:00.000Z", "type": "event_msg",
         "payload": {"type": "agent_message", "message": "x" * 400}}
        for _ in range(300)  # ~126 KB: empurra o diretório para fora da cauda
    ]
    escreve_rollout_codex(tmp_path, casa, [
        {"timestamp": "2026-09-22T21:00:00.000Z", "type": "event_msg",
         "payload": {"type": "item_completed", "item": {"cwd": projeto.as_uri()}}},
        *enchimento,
        {"timestamp": "2026-09-22T22:03:51.070Z", "type": "event_msg",
         "payload": {"type": "task_complete", "last_agent_message": "pronto"}},
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, "codex", cwd=casa))), Transcripts(tmp_path))
    p.poll(AGORA)
    assert store.sessions[0].name == "~/Projetos/WatchAI"
    assert store.sessions[0].status is Status.READY  # e o estado segue vindo da cauda


def test_transcript_ilegivel_nao_derruba_nada(tmp_path):
    pasta = tmp_path / ".claude" / "projects" / "-home-eu-proj"
    pasta.mkdir(parents=True)
    (pasta / "sessao.jsonl").write_text("{isso não é json\n\x00\n", encoding="utf-8")
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(AGORA)
    assert store.sessions[0].agents[0].status is Status.READY  # caiu no sinal do processo


# ---- de quem é cada diário -------------------------------------------------


def test_duas_sessoes_na_mesma_pasta_nao_dividem_o_diario(tmp_path):
    """Duas abas abertas no mesmo projeto é o caso comum de quem separa o
    código dos testes. Casando só por diretório, as duas caíam no arquivo de
    mtime mais alto e um card passava a mostrar a atividade do outro."""
    cedo = AGORA - timedelta(hours=2)
    tarde = AGORA - timedelta(minutes=20)
    escreve_transcript(tmp_path, "/home/eu/proj", [
        abertura(cedo),
        assistente({"type": "text", "text": "pronto"}),
    ], nome="cedo.jsonl")
    escreve_transcript(tmp_path, "/home/eu/proj", [
        abertura(tarde),
        assistente({"type": "tool_use", "id": "t1", "name": "Bash",
                    "input": {"command": "npm test"}}),
    ], nome="tarde.jsonl")

    store = SessionStore()
    fonte = Fonte(snap(
        obs(10, terminal="/dev/pts/1", created=cedo.timestamp()),
        obs(11, terminal="/dev/pts/2", created=tarde.timestamp()),
    ))
    provider(store, fonte, Transcripts(tmp_path)).poll(AGORA)

    atividade = {s.agents[0].pid: s.agents[0].activity for s in store.sessions}
    assert atividade[10] == "task completed"
    assert atividade[11] == "Bash: npm test"


def test_diario_unico_nao_e_emprestado_para_a_sessao_vizinha(tmp_path):
    """Com um diário só para duas sessões, a segunda fica sem — e cai nos
    sinais de processo. Menos informação, mas informação certa: mostrar a
    atividade da vizinha é o pior erro possível num monitor, porque parece
    informação."""
    cedo = AGORA - timedelta(hours=2)
    escreve_transcript(tmp_path, "/home/eu/proj", [
        abertura(cedo),
        assistente({"type": "text", "text": "pronto"}),
    ], nome="cedo.jsonl")

    store = SessionStore()
    fonte = Fonte(snap(
        obs(10, terminal="/dev/pts/1", created=cedo.timestamp()),
        obs(11, terminal="/dev/pts/2", created=(AGORA - timedelta(minutes=20)).timestamp()),
    ))
    provider(store, fonte, Transcripts(tmp_path)).poll(AGORA)

    atividade = {s.agents[0].pid: s.agents[0].activity for s in store.sessions}
    assert atividade[10] == "task completed"
    assert atividade[11] == "idle"


def test_acha_o_diario_pelo_cwd_quando_a_pasta_do_slug_nao_bate(tmp_path):
    """A reserva do casamento por `cwd` lia só a primeira linha, e o formato
    novo do Claude Code abre o arquivo com metadados (`mode`,
    `permission-mode`) que não têm campo nenhum: ela casava com arquivo nenhum
    e virou código morto sem ninguém notar."""
    entrada = assistente({"type": "text", "text": "pronto"})
    entrada["cwd"] = "/home/eu/proj"
    escreve_transcript(tmp_path, "/outro/lugar", [
        {"type": "mode", "mode": "normal", "sessionId": "abc"},
        {"type": "permission-mode", "permissionMode": "default", "sessionId": "abc"},
        entrada,
    ])
    store = SessionStore()
    provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path)).poll(AGORA)
    assert store.sessions[0].agents[0].activity == "task completed"


def test_diario_que_falta_nao_vira_varredura_eterna(tmp_path):
    """Agente sem diário é normal nos primeiros instantes — e permanente numa
    pasta onde nunca houve um. Procurar de novo a cada volta custa uma
    varredura de disco a cada dois segundos, o dia inteiro."""
    from watchai.providers.transcript import Transcripts as T

    t = T(tmp_path)
    buscas = []
    leitor = t.leitores["claude"]
    original = leitor.arquivos
    leitor.arquivos = lambda cwd: (buscas.append(cwd), original(cwd))[1]

    voltas = 200
    for _ in range(voltas):
        assert t.atribuir("claude", "/home/eu/proj", [(10, 0.0)]) == {10: None}

    assert 1 < len(buscas) < voltas // 4  # espaça as tentativas, mas não desiste


# ---- sub-agentes -----------------------------------------------------------


def dispara_subagentes(tmp_path, *estados) -> Path:
    """Uma sessão que lançou sub-agentes: o turno dela fecha na hora, porque a
    ferramenta `Agent` é assíncrona e responde "launched" em um décimo de
    segundo. Cada `estado` vira o diário de um sub-agente."""
    arquivo = escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "tool_use", "id": "t1", "name": "Agent",
                    "input": {"description": "revisar"}}, parou="tool_use"),
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1",
             "content": "Async agent launched successfully."}]}},
        assistente({"type": "text", "text": "disparei os agentes"}),
    ])
    pasta = arquivo.parent / arquivo.stem / "subagents"
    pasta.mkdir(parents=True)
    for i, entrada in enumerate(estados):
        (pasta / f"agent-{i}.jsonl").write_text(json.dumps(entrada) + "\n", encoding="utf-8")
    return pasta


def test_subagente_trabalhando_segura_a_sessao(tmp_path):
    """O diário do principal para de crescer enquanto os sub-agentes rodam, e
    a última linha dele é um `end_turn`: lido sozinho, o card ficava verde —
    "pode vir buscar" — com quatro agentes no meio do trabalho."""
    dispara_subagentes(
        tmp_path,
        assistente({"type": "tool_use", "id": "s1", "name": "Read",
                    "input": {"file_path": "a.py"}}, parou="tool_use"),
        assistente({"type": "thinking", "thinking": "..."}, parou="tool_use"),
    )
    store = SessionStore()
    provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path)).poll(datetime.now())
    assert store.sessions[0].status is Status.WORKING
    assert store.sessions[0].activity == "2 subagents"


def test_subagente_que_terminou_devolve_a_sessao(tmp_path):
    """Todos entregues, o principal volta a mandar: quem terminou é a sessão."""
    dispara_subagentes(tmp_path, assistente({"type": "text", "text": "feito"}))
    store = SessionStore()
    provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path)).poll(datetime.now())
    assert store.sessions[0].status is Status.READY
    assert store.sessions[0].activity == "task completed"


def test_o_cache_nao_congela_quando_so_o_subagente_escreve(tmp_path):
    """Enquanto os sub-agentes trabalham, o diário do principal não cresce.
    Com o cache olhando só o mtime dele, a leitura guardada valia para sempre
    e o trabalho deles nunca chegava à tela."""
    pasta = dispara_subagentes(tmp_path, assistente({"type": "text", "text": "feito"}))
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(datetime.now())
    assert store.sessions[0].status is Status.READY

    # outro sub-agente entra em cena; o diário do principal não muda em nada
    (pasta / "agent-9.jsonl").write_text(json.dumps(assistente(
        {"type": "tool_use", "id": "s9", "name": "Read", "input": {"file_path": "b.py"}},
        parou="tool_use")) + "\n", encoding="utf-8")
    p.poll(datetime.now())
    assert store.sessions[0].status is Status.WORKING
    assert store.sessions[0].activity == "1 subagent"


def test_subagente_parado_nao_anuncia_entrega(tmp_path):
    """Uma corrida interrompida deixa o diário do sub-agente congelado no meio
    da rodada. É o relógio dele que vale, não o do principal: parado, o card
    cai em WAITING — amarelo, sem alarme — em vez de anunciar um "terminou"
    que ninguém entregou."""
    pasta = dispara_subagentes(tmp_path, assistente(
        {"type": "tool_use", "id": "s1", "name": "Read", "input": {"file_path": "a.py"}},
        parou="tool_use",
    ))
    parado = time.time() - 600
    os.utime(pasta / "agent-0.jsonl", (parado, parado))

    store = SessionStore()
    provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path)).poll(datetime.now())
    assert store.sessions[0].status is Status.WAITING


# ---- CPU: pico x trabalho --------------------------------------------------


def test_pico_de_cpu_nao_desfaz_o_terminou(tmp_path):
    """Uma varredura com CPU alta não é trabalho: a TUI redesenha, o contador
    de espera do limite de uso pisca. Sem confirmação, o card alternava entre
    READY e WORKING a cada volta, zerando o contador e enchendo o EVENT
    STREAM."""
    escreve_transcript(tmp_path, "/home/eu/proj", [assistente({"type": "text", "text": "ok"})])
    store = SessionStore()
    fonte = Fonte(snap(obs(10, cpu=10.0, cpu_proprio=10.0)))
    p = provider(store, fonte, Transcripts(tmp_path))
    p.poll(AGORA)

    fonte.s = snap(obs(10, cpu=12.0, cpu_proprio=12.0))
    p.poll(AGORA + timedelta(seconds=2))
    assert store.sessions[0].status is Status.READY

    # seguindo ocupado além da confirmação, aí sim é a resposta sendo gerada
    fonte.s = snap(obs(10, cpu=20.0, cpu_proprio=20.0))
    p.poll(AGORA + timedelta(seconds=8))
    assert store.sessions[0].status is Status.WORKING


def test_navegador_que_a_sessao_deixou_aberto_nao_e_trabalho(tmp_path):
    """A CPU somada da árvore inclui o que o agente abriu e não fechou. Um
    navegador aberto por uma ferramenta gasta CPU para sempre e tem filhos
    para sempre — e prendia a sessão em WORKING mesmo com o turno fechado."""
    escreve_transcript(tmp_path, "/home/eu/proj", [assistente({"type": "text", "text": "ok"})])
    store = SessionStore()

    def com_navegador(cpu):
        return snap(obs(10, cpu=cpu, cpu_proprio=5.0, tool_children=11, tool_label="chrome"))

    fonte = Fonte(com_navegador(10.0))
    p = provider(store, fonte, Transcripts(tmp_path))
    p.poll(AGORA)
    for volta, gasto in enumerate((40.0, 80.0, 120.0), start=1):
        fonte.s = com_navegador(gasto)
        p.poll(AGORA + timedelta(seconds=2 * volta))

    assert store.sessions[0].status is Status.READY
    assert store.sessions[0].activity == "task completed"


def test_sessao_sem_agente_nenhum_responde_offline():
    """`agregar([])` apontava para um `Status.IDLE` que o enum não tem desde
    que o terminal vazio deixou de ser um estado à parte: em vez de responder,
    levantava `AttributeError`."""
    from watchai.models import agregar

    assert agregar([]) is Status.OFFLINE


def test_a_varredura_diz_por_que_veio_vazia(monkeypatch):
    """Lista vazia porque não há agente aberto e lista vazia porque não dá para
    ler a tabela de processos são situações diferentes, com respostas
    diferentes. Diziam a mesma frase — e quem caía na segunda concluía que o
    app é quebrado."""
    import builtins

    from watchai.providers.source import PROCESSOS_PLAUSIVEIS, PsutilSource

    # 1) a varredura levantou: a tela mantém a última leitura e diz isso
    fonte = PsutilSource()
    monkeypatch.setattr(fonte, "_varrer", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    vazio = fonte.snapshot()
    assert vazio.agents == () and vazio.diagnostico == "erro"

    # 2) sem a dependência, a causa é outra e o conserto é de uma linha
    original = builtins.__import__

    def sem_psutil(nome, *args, **kwargs):
        if nome == "psutil":
            raise ImportError("sem psutil")
        return original(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sem_psutil)
    assert PsutilSource().snapshot().diagnostico == "sem-psutil"
    monkeypatch.setattr(builtins, "__import__", original)

    # 3) a leitura funcionou, mas mal enxerga processo: é confinamento, não
    #    ausência de sessão
    class FalsoPsutil:
        class Process:
            def username(self):
                return "eu"

        @staticmethod
        def process_iter(campos):
            return []

    restrito = PsutilSource()._varrer(FalsoPsutil)
    assert restrito.agents == () and restrito.diagnostico == "restrito"
    assert PROCESSOS_PLAUSIVEIS > 1  # o limite existe e não é trivial


def test_a_tela_vazia_explica_a_causa_certa():
    """O texto que aparece quando não há card: uma frase por causa."""
    import asyncio

    from textual.widgets import Static

    from watchai.app import WatchAIApp
    from watchai.notify import Notifier
    from watchai.providers.source import Snapshot as Snap

    class FonteVazia:
        def __init__(self, diagnostico):
            self.s = Snap(diagnostico=diagnostico)

        def snapshot(self):
            return self.s

    async def main(diagnostico, esperado):
        app = WatchAIApp(mock=False, source=FonteVazia(diagnostico),
                         theme_key="watchai", notifier=Notifier(None))
        async with app.run_test(size=(150, 36)) as pilot:
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()
            texto = str(app.screen.query_one("#empty", Static).render())
            assert esperado in texto, f"{diagnostico!r} -> {texto!r}"

    asyncio.run(main("", "no AI session detected"))
    asyncio.run(main("sem-psutil", "psutil is missing"))
    asyncio.run(main("restrito", "cannot read the process table"))
    asyncio.run(main("erro", "the process scan failed"))


# ---- a tela acompanhando o que aparece e some ------------------------------


def test_a_tela_monta_e_desmonta_cards_sozinha():
    """Com dados reais as sessões nascem e morrem com o app aberto — o mock
    nunca exigiu isso, e é onde a tela quebraria."""
    import asyncio

    from watchai.app import WatchAIApp
    from watchai.widgets import SessionCard

    async def main():
        fonte = Fonte(Snapshot())
        app = WatchAIApp(mock=False, source=fonte, theme_key="watchai")
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            assert app.store.sessions == []
            assert app.screen.query_one("#empty").display  # explica em vez de ficar vazia

            fonte.s = snap(obs(10, "claude"), obs(11, "codex"))
            app.provider.apply(fonte.snapshot(), datetime.now())
            app.version += 1
            await pilot.pause()
            await pilot.pause()
            cards = app.screen.query(SessionCard)
            assert len(cards) == 1  # dois agentes, um terminal, um card
            assert not app.screen.query_one("#empty").display
            texto = "\n".join(s.text for s in app.screen._compositor.render_strips())
            assert "agents   2" in texto and "claude" in texto and "codex" in texto

            fonte.s = Snapshot()
            agora = datetime.now()
            app.provider.apply(fonte.snapshot(), agora)
            app.provider.apply(fonte.snapshot(), agora + REMOCAO_FECHADO + timedelta(seconds=1))
            app.version += 1
            await pilot.pause()
            await pilot.pause()
            assert len(app.screen.query(SessionCard)) == 0
            assert app.screen.query_one("#empty").display

    asyncio.run(main())


def test_varredura_em_thread_alimenta_a_tela():
    """O caminho de verdade: `scan()` roda fora da thread da UI e volta."""
    import asyncio

    from watchai.app import WatchAIApp

    async def main():
        app = WatchAIApp(mock=False, source=Fonte(snap(obs(10))), theme_key="watchai")
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert [s.terminal for s in app.store.sessions] == ["pts/1"]
            assert app.provider.transcripts is not None  # detecção completa por padrão

    asyncio.run(main())


def test_o_tempo_do_estado_vem_do_diario(tmp_path):
    """`for MM:SS` tem que contar desde que aconteceu, não desde que o WatchAI
    abriu — senão todo card zera quando você abre o app."""
    agora = datetime.now()
    dez_minutos_atras = agora - timedelta(minutes=10)
    escreve_transcript(tmp_path, "/home/eu/proj", [
        {
            "type": "assistant",
            "timestamp": dez_minutos_atras.astimezone().isoformat(),
            "message": {"content": [{"type": "text", "text": "pronto"}]},
        }
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(agora)
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.READY
    assert abs((agente.status_since - dez_minutos_atras).total_seconds()) < 2
    assert store.sessions[0].status_since == agente.status_since  # o card acompanha


def test_carimbo_no_futuro_nao_vira_contador_negativo(tmp_path):
    agora = datetime.now()
    escreve_transcript(tmp_path, "/home/eu/proj", [
        {
            "type": "assistant",
            "timestamp": (agora + timedelta(hours=3)).astimezone().isoformat(),
            "message": {"content": [{"type": "text", "text": "pronto"}]},
        }
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(agora)
    assert store.sessions[0].agents[0].status_since <= agora


def test_erro_de_api_do_claude_vira_error(tmp_path):
    """Limite de sessão e token expirado param a sessão e não voltam sozinhos —
    é exatamente o que o ERROR existe para avisar."""
    escreve_transcript(tmp_path, "/home/eu/proj", [
        assistente({"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}),
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}},
        {
            "type": "assistant",
            "isApiErrorMessage": True,
            "timestamp": datetime.now().astimezone().isoformat(),
            "message": {"content": [{"type": "text", "text": "You've hit your session limit · resets 10:30pm"}]},
        },
    ])
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(datetime.now())
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.ERROR
    assert "session limit" in agente.activity


def escreve_opencode(home: Path, cwd: str, *, completada: bool, ferramenta: dict | None = None):
    """Monta o storage do OpenCode no layout que o binário declara."""
    raiz = home / ".local" / "share" / "opencode" / "storage" / "session"
    (raiz / "info").mkdir(parents=True, exist_ok=True)
    ses = "ses_abc"
    (raiz / "info" / f"{ses}.json").write_text(
        json.dumps({"id": ses, "directory": cwd, "title": "teste"}), encoding="utf-8"
    )
    msgs = raiz / "message" / ses
    msgs.mkdir(parents=True, exist_ok=True)
    tempo = {"created": 1790000000000}
    if completada:
        tempo["completed"] = 1790000001000
    (msgs / "msg_1.json").write_text(
        json.dumps({"id": "msg_1", "role": "assistant", "time": tempo}), encoding="utf-8"
    )
    if ferramenta:
        partes = raiz / "part" / ses / "msg_1"
        partes.mkdir(parents=True, exist_ok=True)
        (partes / "prt_1.json").write_text(json.dumps(ferramenta), encoding="utf-8")


def test_opencode_terminou(tmp_path):
    escreve_opencode(tmp_path, "/home/eu/proj", completada=True)
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, "opencode"))), Transcripts(tmp_path))
    p.poll(datetime.now())
    assert store.sessions[0].agents[0].status is Status.READY


def test_opencode_com_ferramenta_rodando(tmp_path):
    escreve_opencode(
        tmp_path,
        "/home/eu/proj",
        completada=False,
        ferramenta={"type": "tool", "tool": "bash", "state": {"status": "running",
                                                              "input": {"command": "npm test"}}},
    )
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, "opencode", tool_children=1))), Transcripts(tmp_path))
    p.poll(datetime.now())
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.WORKING and agente.activity == "bash: npm test"


def test_storage_do_opencode_em_formato_estranho_nao_derruba(tmp_path):
    raiz = tmp_path / ".local" / "share" / "opencode" / "storage" / "session" / "info"
    raiz.mkdir(parents=True)
    (raiz / "ses_x.json").write_text("isto não é json", encoding="utf-8")
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10, "opencode"))), Transcripts(tmp_path))
    p.poll(datetime.now())
    assert store.sessions[0].agents[0].status is Status.READY  # caiu no processo


def test_agente_sem_diario_mostra_a_ferramenta_que_esta_rodando():
    """Gemini, Aider e qualquer agente desconhecido: sem diário, o que ele está
    fazendo é o processo filho que ele abriu."""
    store = SessionStore()
    fonte = Fonte(snap(obs(10, "gemini", tool_children=1, tool_label="npm test")))
    p = provider(store, fonte)
    p.poll(AGORA)
    agente = store.sessions[0].agents[0]
    assert agente.status is Status.WORKING and agente.activity == "running npm test"


def test_o_stream_sobrevive_ao_fechamento_do_app(tmp_path, monkeypatch):
    """O que aconteceu enquanto o WatchAI estava fechado continua valendo."""
    import asyncio

    from watchai import config
    from watchai.app import WatchAIApp
    from watchai.notify import Notifier

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))

    async def main():
        fonte = Fonte(snap(obs(10)))
        app = WatchAIApp(mock=False, source=fonte, theme_key="watchai", notifier=Notifier(None))
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            app.provider.apply(fonte.snapshot(), datetime.now())
            app.version += 1
            await pilot.pause()
            assert app.store.events
            app.save_history()

        salvo = config.load_events()
        assert salvo and salvo[0]["short"] == "PROJ"

        outro = WatchAIApp(mock=False, source=Fonte(Snapshot()), theme_key="watchai",
                           notifier=Notifier(None))
        assert outro.store.events  # abriu já com o histórico
        assert outro.store.events[0].session_id == -1  # sem se confundir com sessão nova

    asyncio.run(main())


# ---- ir para a janela da sessão --------------------------------------------


class FocoFalso:
    """Guarda o pedido em vez de mexer em janela nenhuma."""

    def __init__(self) -> None:
        self.pedidos: list[dict] = []
        self.method = "falso"

    @property
    def available(self) -> bool:
        return True

    async def focus(self, **kwargs) -> str:
        self.pedidos.append(kwargs)
        return "janela em evidência"


def test_shift_a_leva_para_a_janela_da_sessao_selecionada():
    import asyncio

    from watchai.app import WatchAIApp
    from watchai.notify import Notifier

    async def main():
        foco = FocoFalso()
        fonte = Fonte(snap(
            obs(10, "claude", "/dev/pts/1", window_pid=4242, window_app="gnome-terminal-server"),
            obs(20, "codex", "/dev/pts/2", cwd="/home/eu/outro", window_pid=4242,
                window_app="gnome-terminal-server"),
        ))
        app = WatchAIApp(mock=False, source=fonte, theme_key="watchai",
                         notifier=Notifier(None), focuser=foco)
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            app.provider.apply(fonte.snapshot(), datetime.now())
            app.version += 1
            await pilot.pause()
            await pilot.pause()
            app.screen.selected = 1  # segundo card
            await pilot.press("A")  # Shift+A
            await app.workers.wait_for_complete()
            assert len(foco.pedidos) == 1
            pedido = foco.pedidos[0]
            assert pedido["pid"] == 4242
            assert pedido["tty"] == "/dev/pts/2"  # a tty da sessão escolhida
            assert pedido["app"] == "gnome-terminal-server"

    asyncio.run(main())


async def _sem_espera(segundos):
    """As esperas do foco existem por causa da animação do compositor; no teste
    elas só somariam segundos."""
    return None


def _lista_gvariant(janelas: list[dict]) -> str:
    """A resposta do `List` como o gdbus entrega: JSON dentro de um GVariant."""
    return "(" + repr(json.dumps(janelas)) + ",)"


class FalsoShell:
    """gdbus de mentira, com a parte que importa: **o foco só muda se a janela
    for mesmo ativada**, e o `Activate` devolve zero de qualquer jeito — que é
    exatamente como o Wayland se comporta quando ignora o pedido.
    """

    def __init__(self, janelas: list[dict], *, extensao: bool = True, recusa: bool = False):
        self.janelas = janelas
        self.extensao = extensao  # a Window Calls está instalada?
        self.recusa = recusa  # o compositor ignora o Activate?
        self.chamadas: list[list[str]] = []

    async def __call__(self, comando, timeout=5.0):
        self.chamadas.append(comando)
        metodo = comando[8].rsplit(".", 1)[-1] if len(comando) > 8 else ""
        args = comando[9:]
        if metodo == "List":
            return (0, _lista_gvariant(self.janelas)) if self.extensao else (1, "")
        if metodo == "Unminimize":
            for j in self.janelas:
                if j["id"] == int(args[0]):
                    j["minimized"] = False
        elif metodo == "Activate" and not self.recusa:
            for j in self.janelas:
                j["focus"] = j["id"] == int(args[0]) and not j.get("minimized", False)
        return 0, "()"

    def args_de(self, metodo: str) -> list[str]:
        return [c[9] for c in self.chamadas if len(c) > 9 and c[8].endswith("." + metodo)]

    @property
    def ordem(self) -> list[str]:
        return [c[8].rsplit(".", 1)[-1] for c in self.chamadas if len(c) > 8]


def janelas_de_um_gnome_terminal(**extra) -> list[dict]:
    """Duas janelas do mesmo processo — o caso do gnome-terminal — e um
    navegador para garantir que o pid filtra."""
    return [
        {"id": 77, "pid": 4242, "wm_class": "gnome-terminal-server",
         "title": "eu@maquina: ~/outro", "focus": False, **extra},
        {"id": 88, "pid": 4242, "wm_class": "gnome-terminal-server",
         "title": "eu@maquina: ~/Projetos/WatchAI", "focus": False, **extra},
        {"id": 99, "pid": 1, "wm_class": "firefox", "title": "web", "focus": False},
    ]


def test_sem_mecanismo_e_sem_tty_o_foco_avisa_que_nao_deu():
    import asyncio

    from watchai.focus import Focuser

    async def main():
        focuser = Focuser(None)  # nenhuma ferramenta de janela nesta máquina
        assert focuser.available is False
        assert await focuser.focus(pid=1, app="", tty="") == "couldn't reach that window"

    asyncio.run(main())


def test_com_varias_janelas_no_mesmo_processo_o_titulo_desempata(monkeypatch):
    """gnome-terminal e konsole hospedam todas as abas num processo só: sem o
    título, o `G` levaria para a janela errada."""
    import asyncio

    from watchai.focus import Focuser

    saida = (
        "0x03000001  0 4242  maquina  ~/outro — bash\n"
        "0x03000002  0 4242  maquina  watchai — claude\n"
        "0x03000003  0 9999  maquina  navegador\n"
    )

    async def falso(comando, timeout=5.0):
        return 0, saida

    monkeypatch.setattr("watchai.focus._rodar", falso)
    focuser = Focuser("wmctrl")
    assert asyncio.run(focuser._janela_wmctrl(4242, "watchai")) == "0x03000002"
    assert asyncio.run(focuser._janela_wmctrl(4242, "inexistente")) == "0x03000001"
    assert asyncio.run(focuser._janela_wmctrl(1, "watchai")) is None


def test_escolher_usa_o_diretorio_antes_do_nome_do_projeto():
    """Duas janelas com o mesmo nome de pasta no fim: o caminho inteiro é o que
    distingue, e por isso vem primeiro."""
    from watchai.focus import escolher

    janelas = [
        {"id": 1, "pid": 9, "title": "eu@maquina: ~/arquivo/WatchAI"},
        {"id": 2, "pid": 9, "title": "eu@maquina: ~/Projetos/WatchAI"},
    ]
    assert escolher(janelas, 9, "WatchAI", "~/Projetos/WatchAI") == 2
    assert escolher(janelas, 9, "WatchAI", None) == 1  # só o nome: o primeiro que casa
    assert escolher(janelas, 7, "WatchAI", None) is None  # nenhuma janela desse pid


def test_gvariant_aceita_os_dois_jeitos_de_aspas():
    """Basta uma janela com apóstrofo no título (um nome de música, por exemplo)
    para o gdbus trocar todo o delimitador de `'` para `"` e escapar as internas.
    Ler só o primeiro caso fazia o app concluir que a extensão não existia."""
    from watchai.focus import _gvariant_string

    simples = "('[{\"title\":\"ola\"}]',)"
    duplas = '("[{\\"title\\":\\"Ngak\'thola\\"}]",)'
    assert json.loads(_gvariant_string(simples))[0]["title"] == "ola"
    assert json.loads(_gvariant_string(duplas))[0]["title"] == "Ngak'thola"
    assert _gvariant_string("nada disso") is None


def test_a_tty_identifica_a_janela_quando_o_titulo_nao_ajuda(monkeypatch):
    """O caso real: quatro janelas no mesmo gnome-terminal, e nenhum título fala
    do projeto — um é o agente dizendo o que faz, outro é o prompt do shell.
    A sessão é reconhecida escrevendo um título único na própria tty."""
    import asyncio

    from watchai.focus import Focuser

    janelas = [
        {"id": 11, "pid": 4242, "title": "eu@maquina: ~", "focus": False},
        {"id": 22, "pid": 4242, "title": "◐ mexendo noutra coisa", "focus": False},
    ]
    shell = FalsoShell(janelas)
    escritas: list[tuple[str, str]] = []

    def falso_titulo(tty, texto):
        escritas.append((tty, texto))
        # Só a janela 22 é desta tty: é ela que recebe a marca.
        janelas[1]["title"] = texto
        return True

    monkeypatch.setattr("watchai.focus._rodar", shell)
    monkeypatch.setattr("watchai.focus.set_title", falso_titulo)
    monkeypatch.setattr("watchai.focus.asyncio.sleep", _sem_espera)

    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(pid=4242, app="gnome-terminal-server", tty="/dev/pts/7", title="projeto")
    )
    assert resultado == "window raised"
    assert shell.args_de("Activate") == ["22"]  # e não a primeira da lista
    # O título de antes volta para a janela: a marca não fica pendurada nela.
    assert escritas[-1] == ("/dev/pts/7", "◐ mexendo noutra coisa")


def test_sem_resposta_ao_osc_o_desempate_por_texto_ainda_vale(monkeypatch):
    """Terminal que ignora o OSC não deixa marca — e aí o caminho antigo, por
    diretório e nome, é o que sobra."""
    import asyncio

    from watchai.focus import Focuser

    shell = FalsoShell(janelas_de_um_gnome_terminal())
    monkeypatch.setattr("watchai.focus._rodar", shell)
    monkeypatch.setattr("watchai.focus.set_title", lambda tty, texto: False)
    monkeypatch.setattr("watchai.focus.asyncio.sleep", _sem_espera)

    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(
            pid=4242,
            app="gnome-terminal-server",
            tty="/dev/pts/7",
            directory="~/Projetos/WatchAI",
        )
    )
    assert resultado == "window raised"
    assert shell.args_de("Activate") == ["88"]


def test_window_calls_foca_a_janela_exata(monkeypatch):
    """Com a extensão instalada dá para focar a janela certa no Wayland — sem
    ela, não há foco preciso nenhum."""
    import asyncio

    from watchai.focus import Focuser

    shell = FalsoShell(janelas_de_um_gnome_terminal())
    monkeypatch.setattr("watchai.focus._rodar", shell)
    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(
            pid=4242,
            app="gnome-terminal-server",
            tty="",
            title="WatchAI",
            directory="~/Projetos/WatchAI",
        )
    )
    assert resultado == "window raised"
    assert shell.args_de("Activate") == ["88"]  # a janela cujo caminho casa


def test_janela_minimizada_e_restaurada_antes_de_ativar(monkeypatch):
    """O caso que motivou tudo: a janela estava minimizada em outro monitor.
    `Activate` sozinho não traz de volta — `Unminimize` tem que vir antes."""
    import asyncio

    from watchai.focus import Focuser

    shell = FalsoShell(janelas_de_um_gnome_terminal(minimized=True))
    monkeypatch.setattr("watchai.focus._rodar", shell)
    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(pid=4242, app="gnome-terminal-server", tty="", directory="~/Projetos/WatchAI")
    )
    assert resultado == "window raised"
    acoes = [m for m in shell.ordem if m in ("Unminimize", "Activate")]
    assert acoes == ["Unminimize", "Activate"]


def test_activate_ignorado_pelo_compositor_nao_vira_sucesso(monkeypatch):
    """O `Activate` devolve zero mesmo quando o Wayland ignora o pedido. Quem
    diz a verdade é o `focus` relido depois — e aqui ele continua falso."""
    import asyncio

    from watchai.focus import Focuser

    shell = FalsoShell(janelas_de_um_gnome_terminal(), recusa=True)
    monkeypatch.setattr("watchai.focus._rodar", shell)
    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(pid=4242, app="gnome-terminal-server", tty="", directory="~/Projetos/WatchAI")
    )
    assert resultado == "the compositor refused to raise the window"


def test_x11_identifica_a_janela_pela_tty(monkeypatch):
    """Marcar a tty não é coisa de Wayland: no X11 o título das janelas tem o
    mesmo problema, e o wmctrl lista do mesmo jeito."""
    import asyncio

    from watchai.focus import Focuser

    janela = {"titulo": "◐ outra coisa"}
    ativadas: list[str] = []

    async def falso(comando, timeout=5.0):
        if comando[:2] == ["wmctrl", "-l"]:
            return 0, f"0x01  0 4242  maq  eu@maq: ~\n0x02  0 4242  maq  {janela['titulo']}\n"
        if comando[:2] == ["wmctrl", "-i"]:
            ativadas.append(comando[-1])
        return 0, ""

    def falso_titulo(tty, texto):
        janela["titulo"] = texto or "◐ outra coisa"
        return True

    monkeypatch.setattr("watchai.focus._rodar", falso)
    monkeypatch.setattr("watchai.focus.set_title", falso_titulo)
    monkeypatch.setattr("watchai.focus.asyncio.sleep", _sem_espera)

    focuser = Focuser("wmctrl")
    assert asyncio.run(focuser.focus(pid=4242, tty="/dev/pts/9")) == "window raised"
    assert ativadas == ["0x02"]  # e não a primeira da lista
    assert janela["titulo"] == "◐ outra coisa"  # o título de antes volta


def test_windows_nao_chama_de_sucesso_o_appactivate_que_falhou(monkeypatch):
    """O PowerShell sai com código zero mesmo quando o AppActivate devolve
    False — era o mesmo sucesso falso do Wayland, com outra roupa. Quem decide
    agora é o que o script imprime."""
    import asyncio

    from watchai.focus import Focuser

    scripts: list[str] = []

    async def falso(comando, timeout=5.0):
        scripts.append(comando[-1])
        return 0, "REFUSED\r\n"

    monkeypatch.setattr("watchai.focus._rodar", falso)
    monkeypatch.setattr("watchai.focus.shutil.which", lambda nome: "/mentira/powershell")
    focuser = Focuser("powershell")
    resultado = asyncio.run(focuser.focus(pid=99, tty=""))
    assert resultado == "the window manager refused to raise the window"
    assert "__PID__" not in scripts[0] and "99" in scripts[0]


def test_windows_confirmado_e_sucesso(monkeypatch):
    import asyncio

    from watchai.focus import Focuser

    async def falso(comando, timeout=5.0):
        return 0, "RAISED\r\n"

    monkeypatch.setattr("watchai.focus._rodar", falso)
    monkeypatch.setattr("watchai.focus.shutil.which", lambda nome: "/mentira/powershell")
    assert asyncio.run(Focuser("powershell").focus(pid=99, tty="")) == "window raised"


def test_mac_marca_a_janela_pela_tty_e_devolve_o_titulo(monkeypatch):
    """No macOS a marca vai dentro do AppleScript: pedir a lista de janelas e
    casar em Python brigaria com nomes que têm vírgula."""
    import asyncio

    from watchai.focus import Focuser

    scripts: list[str] = []
    escritas: list[tuple[str, str]] = []

    async def falso(comando, timeout=5.0):
        if comando[0] == "osascript":  # o tmux é consultado antes; não é o alvo
            scripts.append(comando[-1])
        return 0, "RAISED"

    def falso_titulo(tty, texto):
        escritas.append((tty, texto))
        return True

    monkeypatch.setattr("watchai.focus._rodar", falso)
    monkeypatch.setattr("watchai.focus.set_title", falso_titulo)
    monkeypatch.setattr("watchai.focus.asyncio.sleep", _sem_espera)

    assert asyncio.run(Focuser("osascript").focus(pid=77, tty="/dev/ttys002")) == "window raised"
    assert escritas[0][1].startswith("watchai:")  # marcou
    assert escritas[0][1] in scripts[0]  # e o script procura por ela
    assert "__PID__" not in scripts[0] and "77" in scripts[0]
    # Devolve o título vazio: o Terminal.app volta ao que ele mesmo calcula.
    assert escritas[-1] == ("/dev/ttys002", "")


def test_mac_sem_permissao_de_acessibilidade_nao_promete_nada(monkeypatch):
    """Sem Acessibilidade o osascript sai com erro — e aí sobra o sino."""
    import asyncio

    from watchai.focus import Focuser

    async def falso(comando, timeout=5.0):
        return 1, ""

    monkeypatch.setattr("watchai.focus._rodar", falso)
    monkeypatch.setattr("watchai.focus.set_title", lambda tty, texto: False)
    monkeypatch.setattr("watchai.focus.asyncio.sleep", _sem_espera)
    assert asyncio.run(Focuser("osascript").focus(pid=77, tty="")) == "couldn't reach that window"


def test_a_dica_da_extensao_e_so_no_gnome(monkeypatch):
    """No KDE ou no sway não existe Window Calls: mandar instalar ali seria
    mandar o usuário atrás de algo que não serve."""
    import asyncio

    from watchai.focus import Focuser

    shell = FalsoShell([], extensao=False)
    monkeypatch.setattr("watchai.focus._rodar", shell)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    focuser = Focuser("gdbus")
    resultado = asyncio.run(focuser.focus(pid=4242, app="konsole", tty="", title="x"))
    assert "Window Calls" not in resultado

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    resultado = asyncio.run(focuser.focus(pid=4242, app="konsole", tty="", title="x"))
    assert "Window Calls" in resultado


def test_sem_a_extensao_no_wayland_o_app_nao_promete_foco(monkeypatch):
    """Sem a Window Calls, no Wayland, o `Activate` do terminal só produziria um
    sucesso falso: melhor não tentar e dizer o que falta."""
    import asyncio

    from watchai.focus import Focuser

    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    shell = FalsoShell([], extensao=False)
    monkeypatch.setattr("watchai.focus._rodar", shell)
    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(pid=4242, app="gnome-terminal-server", tty="", title="x")
    )
    assert "install Window Calls" in resultado
    assert shell.args_de("Activate") == []


def test_sem_a_extensao_no_x11_cai_no_activate_do_terminal(monkeypatch):
    """Fora do Wayland o pedido é honrado de verdade, e aí vale tentar."""
    import asyncio

    from watchai.focus import Focuser

    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    shell = FalsoShell([], extensao=False)
    monkeypatch.setattr("watchai.focus._rodar", shell)
    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(pid=4242, app="gnome-terminal-server", tty="", title="x")
    )
    assert resultado == "terminal raised"


def test_o_card_mostra_o_caminho_da_aba_na_borda():
    """O que aparece na tela, não só no modelo: a borda do card traz o caminho
    e o canto segue trazendo o terminal — é o par que distingue duas abas
    abertas no mesmo projeto."""
    import asyncio

    from watchai.app import WatchAIApp
    from watchai.notify import Notifier
    from watchai.widgets import SessionCard

    async def main():
        fonte = Fonte(snap(obs(10, "claude", "/dev/pts/1", cwd="/home/eu/proj")))
        app = WatchAIApp(mock=False, source=fonte, theme_key="watchai", notifier=Notifier(None))
        async with app.run_test(size=(150, 36)) as pilot:
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()
            card = app.screen.query_one(SessionCard)
            assert card.border_title.endswith("/home/eu/proj")
            assert card.border_subtitle == "pts/1"

    asyncio.run(main())


def test_abrir_e_fechar_agente_nao_derruba_a_tela():
    """O caminho real: varredura em thread + reconciliação dos widgets.

    Reconstruir a lista inteira a cada mudança parecia inofensivo, mas
    `remove()` é assíncrono no Textual: remontar na mesma volta recriava
    `card-1` com o antigo ainda no DOM, e o `DuplicateIds` **matava o app** —
    exatamente ao abrir um agente novo com outro já na tela.
    """
    import asyncio

    from watchai.app import WatchAIApp
    from watchai.models import REMOCAO_FECHADO
    from watchai.notify import Notifier
    from watchai.widgets import SessionCard, SessionRow

    async def main():
        fonte = Fonte(snap(obs(10, "claude", "/dev/pts/1")))
        app = WatchAIApp(mock=False, source=fonte, theme_key="watchai", notifier=Notifier(None))
        async with app.run_test(size=(150, 36)) as pilot:
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert len(app.screen.query(SessionCard)) == 1

            # um agente novo abre noutro terminal, com o primeiro na tela
            fonte.s = snap(
                obs(10, "claude", "/dev/pts/1"),
                obs(20, "codex", "/dev/pts/2", cwd="/home/eu/outro"),
            )
            app._last_scan = 0
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.pause()
            assert app.is_running
            assert len(app.screen.query(SessionCard)) == 2
            assert len(app.screen.query(SessionRow)) == 2

            # e agora o primeiro fecha e vence o prazo de permanência
            fonte.s = snap(obs(20, "codex", "/dev/pts/2", cwd="/home/eu/outro"))
            agora = datetime.now()
            app.provider.apply(fonte.snapshot(), agora)
            app.provider.apply(fonte.snapshot(), agora + REMOCAO_FECHADO + timedelta(seconds=1))
            app.version += 1
            await pilot.pause()
            await pilot.pause()
            assert app.is_running
            cards = app.screen.query(SessionCard)
            assert len(cards) == 1
            assert next(iter(cards)).session.terminal == "pts/2"  # sobrou o certo

    asyncio.run(main())


def test_detalhes_abertos_de_uma_sessao_que_some_fecham_sozinhos():
    """O terminal pode fechar e vencer o prazo com os detalhes dele na tela."""
    import asyncio

    from watchai.app import WatchAIApp
    from watchai.models import REMOCAO_FECHADO
    from watchai.notify import Notifier
    from watchai.screens import DetailsScreen

    async def main():
        fonte = Fonte(snap(obs(10, "claude", "/dev/pts/1")))
        app = WatchAIApp(mock=False, source=fonte, theme_key="watchai", notifier=Notifier(None))
        async with app.run_test(size=(150, 36)) as pilot:
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, DetailsScreen)

            fonte.s = Snapshot()
            agora = datetime.now()
            app.provider.apply(fonte.snapshot(), agora)
            app.provider.apply(fonte.snapshot(), agora + REMOCAO_FECHADO + timedelta(seconds=1))
            app.version += 1
            await pilot.pause()
            await pilot.pause()
            assert app.is_running
            assert not isinstance(app.screen, DetailsScreen)  # fechou sozinho

    asyncio.run(main())


def test_varredura_que_explode_nao_mata_o_app():
    """Detecção é a parte que lida com o sistema — ela pode tropeçar. O monitor
    não pode morrer junto."""
    import asyncio

    from watchai.app import WatchAIApp
    from watchai.notify import Notifier

    async def main():
        app = WatchAIApp(mock=False, source=Fonte(snap(obs(10))), theme_key="watchai",
                         notifier=Notifier(None))
        async with app.run_test(size=(150, 36)) as pilot:
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()

            def explode(*args, **kwargs):
                raise RuntimeError("provider quebrou")

            app.provider.apply = explode
            app._last_scan = 0
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.is_running

    asyncio.run(main())


# ---- o registro de agentes (vale em qualquer máquina, não só na minha) ------


def test_reconhece_todos_os_agentes_do_registro():
    """Cada entrada do registro tem que casar pelo próprio nome de programa —
    um erro de digitação na tabela viraria um agente invisível para todo mundo
    que usa aquele CLI."""
    from watchai.providers.agents import KINDS

    for kind in KINDS:
        for programa in kind.programas:
            assert identify([programa]).key == kind.key, programa
            # e nas convenções de Windows e de shim do npm
            assert identify([f"{programa}.exe"]).key == kind.key, programa
            assert identify([f"C:\\Users\\eu\\AppData\\{programa}.cmd"]).key == kind.key
        for pacote in kind.pacotes:
            assert identify(["node", f"/home/eu/node_modules/{pacote}/cli.js"]).key == kind.key


def test_cobre_os_agentes_que_o_usuario_citou():
    for programa, chave in (
        ("antigravity", "antigravity"),
        ("opencode", "opencode"),
        ("grok", "grok"),
        ("deepseek", "deepseek"),
        ("copilot", "copilot"),
    ):
        assert identify([programa]).key == chave
    # `gh copilot` é subcomando: o agente não é o programa executado
    assert identify(["gh", "copilot", "suggest"]).key == "copilot"
    # e por runtime, como o npm instala
    assert identify(["npx", "@vibe-kit/grok-cli"]).key == "grok"


def test_nome_de_modelo_nao_e_agente():
    """`ollama run deepseek-r1` roda um modelo, não uma sessão de agente — e
    um editor com um arquivo de mesmo nome também não."""
    assert identify(["ollama", "run", "deepseek-r1"]) is None
    assert identify(["nvim", "grok.md"]) is None
    assert identify(["bash", "-c", "echo antigravity"]) is None


def test_usuario_acrescenta_o_proprio_agente(tmp_path, monkeypatch):
    """Ninguém deveria esperar uma release para ver a própria sessão na tela."""
    import json

    from watchai import config
    from watchai.providers import agents

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    destino = tmp_path / "watchai"
    destino.mkdir()
    (destino / "config.json").write_text(
        json.dumps({"agents": {"meu-agente": ["zzagente"], "claude": ["claude-dev"]}}),
        encoding="utf-8",
    )
    assert identify(["zzagente"]) is None  # antes de registrar, desconhecido
    try:
        agents.registrar(config.load_agents())
        assert identify(["zzagente"]).key == "meu-agente"
        assert identify(["claude-dev"]).key == "claude"  # apelido de um conhecido
    finally:  # o registro é global ao processo: não pode vazar para outro teste
        agents.POR_PROGRAMA.pop("zzagente", None)
        agents.POR_PROGRAMA.pop("claude-dev", None)
        agents.POR_CHAVE.pop("meu-agente", None)


def test_agente_sem_terminal_ainda_vira_card():
    """Agente rodando dentro de uma IDE não tem tty: a sessão passa a ser
    identificada pelo próprio processo, em vez de virar um card sem nome."""
    from watchai.providers.source import rotulo_terminal

    assert rotulo_terminal("/dev/pts/3", None, None) == "pts/3"
    assert rotulo_terminal(None, "pwsh", 4312) == "pwsh #4312"
    assert rotulo_terminal(None, None, None, "antigravity", 99) == "antigravity #99"
    assert rotulo_terminal(None, None, None) == "?"


def test_ordenar_por_atencao_sobe_quem_precisa_de_voce():
    """A regra pura: quem pede você primeiro sobe, e dentro do mesmo estado a
    ordem de descoberta continua valendo — para o card se mexer o mínimo."""
    from watchai.models import ordenar
    from watchai.models.session import Session

    def sessao(id, status):
        return Session(
            id=id, name=f"s{id}", short=f"S{id}", status=status, project="",
            directory="", pid=id, started_at=AGORA, status_since=AGORA, activity="",
        )

    sessoes = [
        sessao(1, Status.WORKING),
        sessao(2, Status.ERROR),
        sessao(3, Status.WORKING),
        sessao(4, Status.READY),
    ]
    assert [s.id for s in ordenar(sessoes, False)] == [1, 2, 3, 4]  # descoberta
    assert [s.id for s in ordenar(sessoes, True)] == [2, 4, 1, 3]  # ERROR, READY, resto


def test_a_tecla_de_ordenar_reordena_os_cards_sem_perder_a_selecao():
    """Reordenar não pode trocar o card selecionado debaixo do cursor: a
    seleção segue a sessão, não a posição."""
    import asyncio

    from watchai.app import WatchAIApp
    from watchai.notify import Notifier
    from watchai.widgets import SessionCard

    async def main():
        fonte = Fonte(snap(
            obs(10, "claude", "/dev/pts/1", cwd="/home/eu/a"),
            obs(20, "claude", "/dev/pts/2", cwd="/home/eu/b"),
        ))
        app = WatchAIApp(mock=False, source=fonte, theme_key="watchai", notifier=Notifier(None))
        async with app.run_test(size=(150, 36)) as pilot:
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()

            sessoes = app.store.sessions
            sessoes[0].status, sessoes[1].status = Status.WORKING, Status.ERROR
            # seleciona a de baixo (a que vai subir ao ordenar)
            app.screen.selected = 1
            escolhida = app.selected_session().id

            await pilot.press("s")
            await pilot.pause()
            assert app.sort_on is True
            ordem = [c.session.id for c in app.screen.query(SessionCard)]
            assert ordem == [sessoes[1].id, sessoes[0].id]  # o ERROR subiu
            assert app.selected_session().id == escolhida  # e continua a mesma

            await pilot.press("s")
            await pilot.pause()
            assert app.sort_on is False
            assert [c.session.id for c in app.screen.query(SessionCard)] == [
                sessoes[0].id, sessoes[1].id
            ]

    asyncio.run(main())


def test_dentro_do_tmux_o_painel_certo_e_selecionado(monkeypatch):
    """A aba de um gnome-terminal não é endereçável por lugar nenhum; um painel
    do tmux é. E a tty que tem janela é a do **cliente**: a do painel é um pty
    que não pertence a janela nenhuma, então marcar o título nela não acharia
    nada."""
    import asyncio

    from watchai.focus import Focuser

    comandos: list[list[str]] = []

    async def falso(comando, timeout=5.0):
        comandos.append(comando)
        if comando[:2] == ["tmux", "list-panes"]:
            return 0, "/dev/pts/6\twt:0.1\twt\n/dev/pts/9\twt:1.0\twt\n"
        if comando[:2] == ["tmux", "list-clients"]:
            return 0, "/dev/pts/11\n"
        return 0, ""

    monkeypatch.setattr("watchai.focus._rodar", falso)
    focuser = Focuser(None)

    assert asyncio.run(focuser._tmux("/dev/pts/6")) == "/dev/pts/11"
    assert ["tmux", "select-window", "-t", "wt:0.1"] in comandos
    assert ["tmux", "select-pane", "-t", "wt:0.1"] in comandos

    # tty que não é painel de tmux nenhum não pode mexer na seleção de ninguém
    comandos.clear()
    assert asyncio.run(focuser._tmux("/dev/pts/99")) is None
    assert not [c for c in comandos if "select-pane" in c]


def test_sem_tmux_o_foco_segue_como_antes(monkeypatch):
    """Máquina sem tmux, ou com o servidor parado: o `list-panes` falha e o
    caminho continua o de sempre, sem nada de novo para dar errado."""
    import asyncio

    from watchai.focus import Focuser

    async def falso(comando, timeout=5.0):
        if comando[0] == "tmux":
            return 127, ""  # comando não existe
        return 0, ""

    monkeypatch.setattr("watchai.focus._rodar", falso)
    assert asyncio.run(Focuser(None)._tmux("/dev/pts/6")) is None
