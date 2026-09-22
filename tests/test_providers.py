"""Detecção real: reconhecimento de agente, agrupamento por terminal e estados.

Nada aqui olha a máquina de quem roda: a tabela de processos é injetada e o
relógio é um argumento. Os transcripts são arquivos de mentira num `tmp_path`.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
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
    assert primeiro.name == "PROJ"  # o título é o projeto, não a IA
    assert store.sessions[1].name == "OUTRO"


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


def test_terminal_aberto_sem_agente_fica_ocioso():
    store = SessionStore()
    fonte = Fonte(snap(obs(10)))
    p = provider(store, fonte)
    p.poll(AGORA)
    fonte.s = snap(terminais=["/dev/pts/1"])  # agente saiu, aba continua aberta
    p.poll(AGORA + timedelta(seconds=5))
    sessao = store.sessions[0]
    assert sessao.status is Status.IDLE
    assert sessao.agents == [] and sessao.closed_at is None


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


def escreve_transcript(home: Path, cwd: str, entradas: list[dict]) -> Path:
    slug = "-" + cwd.strip("/").replace("/", "-")
    pasta = home / ".claude" / "projects" / slug
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "sessao.jsonl"
    arquivo.write_text("\n".join(json.dumps(e) for e in entradas) + "\n", encoding="utf-8")
    return arquivo


def assistente(*blocos):
    return {"type": "assistant", "message": {"content": list(blocos)}}


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


def test_transcript_ilegivel_nao_derruba_nada(tmp_path):
    pasta = tmp_path / ".claude" / "projects" / "-home-eu-proj"
    pasta.mkdir(parents=True)
    (pasta / "sessao.jsonl").write_text("{isso não é json\n\x00\n", encoding="utf-8")
    store = SessionStore()
    p = provider(store, Fonte(snap(obs(10))), Transcripts(tmp_path))
    p.poll(AGORA)
    assert store.sessions[0].agents[0].status is Status.READY  # caiu no sinal do processo


def test_sem_psutil_ou_com_erro_a_varredura_devolve_vazio(monkeypatch):
    from watchai.providers.source import PsutilSource

    fonte = PsutilSource()
    monkeypatch.setattr(fonte, "_varrer", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    assert fonte.snapshot() == Snapshot()


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


def test_sem_mecanismo_e_sem_tty_o_foco_avisa_que_nao_deu():
    import asyncio

    from watchai.focus import Focuser

    async def main():
        focuser = Focuser(None)  # nenhuma ferramenta de janela nesta máquina
        assert focuser.available is False
        assert await focuser.focus(pid=1, app="", tty="") == "não consegui chegar nessa janela"

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


def test_window_calls_foca_a_janela_exata(monkeypatch):
    """Com a extensão instalada dá para focar a janela certa no Wayland —
    sem ela, o melhor possível é levantar o terminal."""
    import asyncio

    from watchai.focus import Focuser

    chamadas: list[list[str]] = []
    lista = (
        '(\'[{"id":77,"pid":4242,"wm_class":"gnome-terminal-server","title":"outro"},'
        '{"id":88,"pid":4242,"wm_class":"gnome-terminal-server","title":"watchai — claude"},'
        '{"id":99,"pid":1,"wm_class":"firefox","title":"web"}]\',)'
    )

    async def falso(comando, timeout=5.0):
        chamadas.append(comando)
        if comando[-1].endswith(".List"):
            return 0, lista
        return 0, "()"

    monkeypatch.setattr("watchai.focus._rodar", falso)
    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(pid=4242, app="gnome-terminal-server", tty="", title="watchai")
    )
    assert resultado == "janela em evidência"
    activate = [c for c in chamadas if c[-2].endswith(".Activate")]
    assert activate and activate[0][-1] == "88"  # a janela cujo título casa


def test_sem_a_extensao_cai_no_activate_do_terminal(monkeypatch):
    import asyncio

    from watchai.focus import Focuser

    async def falso(comando, timeout=5.0):
        if comando[-1].endswith(".List"):
            return 1, ""  # extensão não instalada
        return 0, "()"

    monkeypatch.setattr("watchai.focus._rodar", falso)
    focuser = Focuser("gdbus")
    resultado = asyncio.run(
        focuser.focus(pid=4242, app="gnome-terminal-server", tty="", title="x")
    )
    assert resultado == "terminal chamado para a frente"
