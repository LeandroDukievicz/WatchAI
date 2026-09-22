"""Smoke tests do protótipo visual (rodam headless, sem terminal real).

    pip install pytest && pytest -q
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

import watchai
from watchai import config
from watchai.app import WatchAIApp
from watchai.format import ellipsize
from watchai.layout import Layout, layout_for
from watchai.models import Status
from watchai.notify import Notifier
from watchai.sound import Alert
from watchai.screens import DetailsScreen, HelpScreen, ThemeScreen
from watchai.theme import DEFAULT, PALETTES, use
from watchai.widgets import SessionCard, SessionRow, StatusLight, TrafficLight
from watchai.widgets.traffic_light import AMBER_LAMP, GREEN_LAMP, RED_LAMP


def run(coro):
    return asyncio.run(coro)


def test_ellipsize():
    assert ellipsize("telegram-downloader", 16) == "telegram-downlo…"
    assert ellipsize("abc", 16) == "abc"
    assert ellipsize("abc", 1) == "…"


def test_breakpoints():
    assert layout_for(150) is Layout.LARGE and Layout.LARGE.columns == 3
    assert layout_for(130) is Layout.LARGE
    assert layout_for(129) is Layout.MEDIUM and Layout.MEDIUM.columns == 2
    assert layout_for(90) is Layout.MEDIUM
    assert layout_for(89) is Layout.SMALL and Layout.SMALL.columns == 1
    assert layout_for(60) is Layout.SMALL
    assert layout_for(59) is Layout.TINY and Layout.TINY.compact


def test_every_status_has_color_symbol_label():
    for s in Status:
        assert s.label and s.color.startswith("#") and s.symbol


def test_responsive_grid_and_navigation():
    async def main():
        app = WatchAIApp(seed=1, mock=True)
        async with app.run_test(size=(150, 40)) as pilot:
            await pilot.pause()
            dash = app.screen
            grid = dash.query_one("#cards")
            assert grid.styles.grid_size_columns == 3
            assert len(dash.query(SessionCard)) == 6

            await pilot.press("right")
            assert dash.selected == 1
            await pilot.press("down")  # 3 colunas: desce uma linha
            assert dash.selected == 4
            await pilot.press("left", "up")
            assert dash.selected == 0

            await pilot.resize_terminal(110, 36)
            await pilot.pause()
            assert grid.styles.grid_size_columns == 2
            await pilot.resize_terminal(75, 36)
            await pilot.pause()
            assert grid.styles.grid_size_columns == 1
            await pilot.resize_terminal(50, 30)
            await pilot.pause()
            assert all(c.compact for c in dash.query(SessionCard))

    run(main())


def test_views_panels_details_help():
    async def main():
        app = WatchAIApp(seed=1, mock=True)
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause()
            dash = app.screen
            await pilot.press("v")
            assert dash.view == "list" and dash.query_one("#rows").display
            assert len(dash.query(SessionRow)) == 6
            await pilot.press("v")
            assert dash.view == "cards"

            await pilot.press("tab")
            assert dash.panel == "events"
            await pilot.press("tab")
            assert dash.panel == "sessions"

            await pilot.press("enter")
            assert isinstance(app.screen, DetailsScreen)
            await pilot.press("escape")
            assert isinstance(app.screen, type(dash))

            await pilot.press("question_mark")
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, HelpScreen)

    run(main())


def test_simulation_never_breaks_the_ui():
    async def main():
        app = WatchAIApp(seed=7, mock=True)
        async with app.run_test(size=(130, 40)) as pilot:
            await pilot.pause()
            now = datetime.now()
            for i in range(300):
                now += timedelta(seconds=6)
                app.simulator.step(now)
                app.simulator.settle(now)
                app.version += 1
                if i % 30 == 0:
                    await pilot.pause()
            await pilot.pause()
            counts = app.store.counts()
            assert sum(counts.values()) == 6
            lights = app.screen.query(StatusLight)
            assert len(lights) >= 12  # 6 cards + 6 rows

    run(main())


def test_semaforo_acende_a_lampada_certa():
    esperado = {
        Status.ERROR: RED_LAMP,
        Status.WORKING: AMBER_LAMP,
        Status.WAITING: AMBER_LAMP,
        Status.STARTING: AMBER_LAMP,
        Status.INPUT: AMBER_LAMP,
        Status.READY: GREEN_LAMP,
        Status.OFFLINE: None,  # encerrada: nenhuma acesa
    }
    for status, lamp in esperado.items():
        assert TrafficLight(status).lit_lamp() == lamp, status


def test_semaforo_do_input_pisca_e_os_outros_nao():
    """Fases do piscar: 1 s aceso / 1 s apagado (tick do app = 0,5 s)."""
    piscando, fixo = TrafficLight(Status.INPUT), TrafficLight(Status.WORKING)
    fases, constante = [], []
    for tick in range(8):
        piscando.set_reactive(TrafficLight.tick, tick)
        fixo.set_reactive(TrafficLight.tick, tick)
        fases.append(piscando.lit_lamp())
        constante.append(fixo.lit_lamp())
    assert fases == [AMBER_LAMP, AMBER_LAMP, None, None] * 2
    assert constante == [AMBER_LAMP] * 8


def test_semaforo_so_acompanha_o_tick_quando_pisca():
    """Quem não pisca não repinta a cada tick."""

    async def main():
        app = WatchAIApp(seed=1, mock=True)
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            cards = {c.session.short: c for c in app.screen.query(SessionCard)}
            app.tick += 1
            await pilot.pause()
            assert cards["OPENCODE"]._traffic.tick == app.tick  # INPUT: segue o app
            assert cards["CLAUDE"]._traffic.tick == 0  # WORKING: nada a animar

    run(main())


def test_layout_sem_vao_morto():
    """EVENT STREAM encosta nos cards, keybar na última linha, card de 48 colunas."""

    async def main():
        app = WatchAIApp(seed=1, mock=True)
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            dash = app.screen
            area = dash.query_one("#sessions-area").region
            events = dash.query_one("#events").region
            assert events.y == area.y + area.height
            assert dash.query_one("#keybar").region.y == 35
            card = next(iter(dash.query(SessionCard)))
            assert card.region.width == 48
            assert card.region.height == 10  # a altura vem do semáforo (8 linhas)
            assert card.query_one(TrafficLight).region.width == 9

    run(main())


def test_stream_nunca_e_empurrado_para_fora_da_tela():
    """Em 1 coluna os 6 cards não cabem: a área rola, o stream continua inteiro."""

    async def main():
        app = WatchAIApp(seed=1, mock=True)
        async with app.run_test(size=(60, 30)) as pilot:
            await pilot.pause()
            dash = app.screen
            events = dash.query_one("#events").region
            assert events.height >= 8
            assert events.y + events.height <= 30
            assert dash.query_one("#sessions-area").show_vertical_scrollbar
            assert dash.query_one("#header").region.y == 0

    run(main())


def test_no_estreito_sobram_nome_projeto_e_semaforo():
    """Estreitando, o semáforo é a última coisa a sair — é ele que dá o estado
    sem texto nenhum. Quem sai é a linha de estado e o resto do corpo."""

    async def main():
        app = WatchAIApp(seed=1, mock=True)
        async with app.run_test(size=(50, 28)) as pilot:
            await pilot.pause()
            assert all(t.display for t in app.screen.query(TrafficLight))
            assert not any(
                luz.display for luz in app.screen.query(".card-light")
            )  # a linha "◐ WORKING" sai
            card = next(iter(app.screen.query(SessionCard)))
            texto = "\n".join(s.text for s in app.screen._compositor.render_strips())
            assert card.session.short in texto and card.session.project in texto

            await pilot.resize_terminal(150, 36)
            await pilot.pause()
            assert all(t.display for t in app.screen.query(TrafficLight))
            assert all(luz.display for luz in app.screen.query(".card-light"))

    run(main())


class AlertaFalso(Alert):
    """Conta os bips em vez de tocar, e guarda o timbre de cada um."""

    def __init__(self) -> None:
        super().__init__(command=["(falso)"])
        self.bips = 0
        self.timbres: list[str] = []

    async def play(self, kind: str = "ready") -> None:
        self.bips += 1
        self.timbres.append(kind)


def _app_com_bip(seed: int = 1) -> tuple[WatchAIApp, AlertaFalso]:
    alerta = AlertaFalso()
    return WatchAIApp(seed=seed, alert=alerta, mock=True, notifier=Notifier(None)), alerta


async def _vira_ready(app, pilot, short: str) -> None:
    """Força uma sessão a entrar em READY pelo mesmo caminho da integração real."""
    session = next(s for s in app.store.sessions if s.short == short)
    app.store.transition(session, Status.READY, "task completed", datetime.now())
    app.version += 1
    await pilot.pause()
    await pilot.pause()


def test_bipa_quando_uma_sessao_fica_ready():
    async def main():
        app, alerta = _app_com_bip()
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            assert alerta.bips == 0  # CODEX já nasce READY e não deve bipar
            await _vira_ready(app, pilot, "CLAUDE")
            assert alerta.bips == 1

    run(main())


def test_avisa_nos_tres_estados_que_param_voce_com_timbres_diferentes():
    """READY, INPUT e ERROR avisam coisas diferentes: mesmo som obrigaria a
    olhar a tela para saber qual foi."""

    async def main():
        app, alerta = _app_com_bip()
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            claude = next(s for s in app.store.sessions if s.short == "CLAUDE")
            for status in (Status.INPUT, Status.WORKING, Status.ERROR):
                app.store.transition(claude, status, "seguindo", datetime.now())
                app.version += 1
                await pilot.pause()
                await pilot.pause()
            assert alerta.timbres == ["input", "error"]  # WORKING no meio não avisa

    run(main())


def test_nao_avisa_em_estado_que_nao_pede_voce():
    async def main():
        app, alerta = _app_com_bip()
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            claude = next(s for s in app.store.sessions if s.short == "CLAUDE")
            for status in (Status.WAITING, Status.WORKING, Status.OFFLINE):
                app.store.transition(claude, status, "seguindo", datetime.now())
                app.version += 1
                await pilot.pause()
            assert alerta.bips == 0

    run(main())


def test_tecla_b_silencia_o_bip():
    async def main():
        app, alerta = _app_com_bip()
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            await pilot.press("b")  # desliga
            await pilot.pause()
            assert app.sound_on is False
            await _vira_ready(app, pilot, "CLAUDE")
            assert alerta.bips == 0
            await pilot.press("b")  # religa (confirma com um bip)
            await pilot.pause()
            await pilot.pause()
            assert app.sound_on is True
            assert alerta.bips == 1

    run(main())


def test_rajada_de_ready_vira_um_bip_so():
    async def main():
        app, alerta = _app_com_bip()
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            for short in ("CLAUDE", "GEMINI", "AIDER"):
                await _vira_ready(app, pilot, short)
            assert alerta.bips == 1  # debounce de 1 s

    run(main())


def test_sem_player_no_sistema_nao_quebra(monkeypatch):
    """Máquina sem áudio: sobra o bell do terminal, e nada estoura."""
    from watchai import sound as sound_mod

    monkeypatch.setattr("shutil.which", lambda _: None)
    assert sound_mod.find_player() is None
    alerta = Alert(command=None)
    assert alerta.available is False
    asyncio.run(alerta.play())  # no-op silencioso


# ---- temas -----------------------------------------------------------------


def test_toda_paleta_cobre_as_variaveis_do_tcss():
    """O TCSS é parseado com as variáveis da paleta ativa: uma faltando levanta
    UnresolvedVariableError e derruba a tela inteira, não só a cor."""
    tcss = (Path(watchai.__file__).parent / "styles" / "app.tcss").read_text()
    usadas = set(re.findall(r"\$aw-[a-z0-9-]+", tcss))
    assert usadas  # se o CSS parar de usar $aw-*, este teste virou mentira
    for palette in PALETTES:
        fornecidas = {f"${name}" for name in palette.css_variables()}
        assert not usadas - fornecidas, palette.key


def test_status_resolve_a_cor_na_paleta_ativa():
    """Nenhum estado carrega cor fixa: todos leem a vaga na paleta do momento."""
    for palette in PALETTES:
        use(palette)
        assert Status.READY.color == palette.green
        assert Status.WORKING.color == palette.cyan
        assert Status.INPUT.color == palette.magenta
        assert Status.OFFLINE.color == palette.ghost


def test_tema_desconhecido_cai_no_padrao():
    assert use("nao-existe-ainda") is DEFAULT
    assert config.load_theme() is None  # config vazia não inventa tema


def test_todos_os_temas_desenham_a_tela_inteira():
    async def main():
        for palette in PALETTES:
            app = WatchAIApp(seed=3, mock=True, theme_key=palette.key)
            async with app.run_test(size=(150, 36)) as pilot:
                await pilot.pause()
                linhas = [s.text for s in app.screen._compositor.render_strips()]
                assert len(linhas) == 36, palette.key
                assert any("SESSIONS" in linha for linha in linhas), palette.key
                assert any("EVENT STREAM" in linha for linha in linhas), palette.key

    run(main())


def test_seletor_faz_preview_ao_vivo_e_esc_desfaz():
    """Mover a seleção aplica o tema atrás do modal; ESC volta ao que era."""

    async def main():
        app = WatchAIApp(seed=1, mock=True, theme_key="watchai")
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            await pilot.press("t")
            await pilot.pause()
            assert isinstance(app.screen, ThemeScreen)
            await pilot.press("down")
            await pilot.pause()
            seguinte = PALETTES[1]
            assert app.palette_key == seguinte.key
            assert Status.READY.color == seguinte.green  # o dashboard já trocou
            await pilot.press("escape")
            await pilot.pause()
            assert app.palette_key == "watchai"
            assert not isinstance(app.screen, ThemeScreen)
            assert config.load_theme() is None  # cancelar não grava nada

    run(main())


def test_enter_grava_o_tema_para_a_proxima_execucao():
    async def main():
        alvo = PALETTES[3]
        app = WatchAIApp(seed=1, mock=True, theme_key="watchai")
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            await pilot.press("t")
            await pilot.pause()
            for _ in range(3):
                await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            assert not isinstance(app.screen, ThemeScreen)
            assert app.palette_key == alvo.key
            assert config.load_theme() == alvo.key

        # nova execução, sem theme_key: tem que nascer no tema salvo
        assert WatchAIApp(seed=1, mock=True).palette_key == alvo.key

    run(main())


def test_modal_de_temas_cabe_na_caixa():
    """O rodapé já estourou as 38 colunas úteis e quebrou para a linha de baixo —
    uma linha a mais na caixa é o sintoma que este teste vigia."""

    async def main():
        app = WatchAIApp(seed=1, mock=True, theme_key="watchai")
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            await pilot.press("t")
            await pilot.pause()
            r = app.screen.query_one("#themes").region
            linhas = [s.text for s in app.screen._compositor.render_strips()]
            caixa = [linha[r.x : r.x + r.width] for linha in linhas[r.y : r.y + r.height]]
            # borda (2) + padding (2) + um tema por linha + branco + rodapé
            assert len(caixa) == len(PALETTES) + 6
            assert any("ESC cancel" in linha for linha in caixa)
            for palette in PALETTES:
                assert any(palette.label in linha for linha in caixa), palette.key

    run(main())


class NotificadorFalso(Notifier):
    """Guarda as notificações em vez de chamar o sistema."""

    def __init__(self) -> None:
        super().__init__("falso")
        self.enviadas: list[tuple[str, str, str]] = []

    async def send(self, title: str, body: str, kind: str = "ready") -> None:
        self.enviadas.append((title, body, kind))


def test_notifica_so_quando_voce_nao_esta_olhando():
    """Com o WatchAI em foco a notificação é ruído: você já está vendo."""

    async def main():
        alerta, avisos = AlertaFalso(), NotificadorFalso()
        app = WatchAIApp(seed=1, alert=alerta, mock=True, notifier=avisos)
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            app.on_app_focus()
            await _vira_ready(app, pilot, "CLAUDE")
            assert alerta.bips == 1 and avisos.enviadas == []  # bipa, não notifica

            app.on_app_blur()
            await _vira_ready(app, pilot, "GEMINI")
            await pilot.pause()
            assert len(avisos.enviadas) == 1
            titulo, corpo, timbre = avisos.enviadas[0]
            assert titulo == "READY · GEMINI" and timbre == "ready" and corpo

    run(main())


def test_o_interruptor_de_avisos_fica_salvo():
    async def main():
        app = WatchAIApp(seed=1, alert=AlertaFalso(), mock=True, notifier=NotificadorFalso())
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            assert app.sound_on is True  # padrão: quem instala um monitor quer aviso
            await pilot.press("b")
            await pilot.pause()
            assert app.sound_on is False
            from watchai import config

            assert config.load_alerts() is False

        # nova execução lê o que ficou salvo
        outro = WatchAIApp(seed=1, alert=AlertaFalso(), mock=True, notifier=NotificadorFalso())
        assert outro.sound_on is False

    run(main())


def test_notificador_que_morre_no_meio_nao_derruba_o_app():
    """O processo do toast pode sumir sozinho antes do timeout: matar um
    processo já morto levanta ProcessLookupError e isso chegava como falha de
    worker — no CI do Windows, derrubando a suíte."""

    async def main():
        from watchai.notify import Notifier

        class ProcessoFantasma:
            async def wait(self):
                await asyncio.sleep(3600)  # nunca termina: força o timeout

            def kill(self):
                raise ProcessLookupError

        async def spawn(*args, **kwargs):
            return ProcessoFantasma()

        import watchai.notify as modulo

        original, espera = modulo.asyncio.create_subprocess_exec, modulo.TIMEOUT
        modulo.asyncio.create_subprocess_exec = spawn
        modulo.TIMEOUT = 0.05
        try:
            avisos = Notifier("notify-send")
            await asyncio.wait_for(avisos.send("t", "b", "ready"), timeout=5)
        finally:
            modulo.asyncio.create_subprocess_exec = original
            modulo.TIMEOUT = espera

    run(main())
