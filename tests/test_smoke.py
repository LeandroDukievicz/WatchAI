"""Smoke tests do protótipo visual (rodam headless, sem terminal real).

    pip install pytest && pytest -q
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from watchai.app import WatchAIApp
from watchai.format import ellipsize
from watchai.layout import Layout, layout_for
from watchai.models import Status
from watchai.sound import Alert
from watchai.screens import DetailsScreen, HelpScreen
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
        app = WatchAIApp(seed=1)
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
        app = WatchAIApp(seed=1)
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
        app = WatchAIApp(seed=7)
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
        app = WatchAIApp(seed=1)
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
        app = WatchAIApp(seed=1)
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            dash = app.screen
            area = dash.query_one("#sessions-area").region
            events = dash.query_one("#events").region
            assert events.y == area.y + area.height
            assert dash.query_one("#keybar").region.y == 35
            card = next(iter(dash.query(SessionCard)))
            assert card.region.width == 48
            assert card.region.height == 7
            assert card.query_one(TrafficLight).region.width == 5

    run(main())


def test_stream_nunca_e_empurrado_para_fora_da_tela():
    """Em 1 coluna os 6 cards não cabem: a área rola, o stream continua inteiro."""

    async def main():
        app = WatchAIApp(seed=1)
        async with app.run_test(size=(60, 30)) as pilot:
            await pilot.pause()
            dash = app.screen
            events = dash.query_one("#events").region
            assert events.height >= 8
            assert events.y + events.height <= 30
            assert dash.query_one("#sessions-area").show_vertical_scrollbar
            assert dash.query_one("#header").region.y == 0

    run(main())


def test_semaforo_some_no_modo_compacto():
    async def main():
        app = WatchAIApp(seed=1)
        async with app.run_test(size=(50, 28)) as pilot:
            await pilot.pause()
            assert not any(t.display for t in app.screen.query(TrafficLight))
            await pilot.resize_terminal(150, 36)
            await pilot.pause()
            assert all(t.display for t in app.screen.query(TrafficLight))

    run(main())


class AlertaFalso(Alert):
    """Conta os bips em vez de tocar."""

    def __init__(self) -> None:
        super().__init__(command=["(falso)"])
        self.bips = 0

    async def play(self) -> None:
        self.bips += 1


def _app_com_bip(seed: int = 1) -> tuple[WatchAIApp, AlertaFalso]:
    alerta = AlertaFalso()
    return WatchAIApp(seed=seed, alert=alerta), alerta


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


def test_nao_bipa_em_estado_que_nao_e_ready():
    async def main():
        app, alerta = _app_com_bip()
        async with app.run_test(size=(150, 36)) as pilot:
            await pilot.pause()
            claude = next(s for s in app.store.sessions if s.short == "CLAUDE")
            for status in (Status.WAITING, Status.INPUT, Status.ERROR, Status.OFFLINE):
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
