"""WatchAI — monitor de sessões de IA no terminal.

Por padrão o app **detecta de verdade**: varre a tabela de processos, agrupa os
agentes por terminal e alimenta o `SessionStore`. Nada aqui fala com IA nenhuma
— nem API, nem hook, nem configuração dos agentes.

Com `--mock` o app volta a rodar com dados simulados (`watchai.mock`), que é
como se avalia a interface em movimento sem depender do que está aberto.
"""

from __future__ import annotations

from datetime import datetime
from time import monotonic

from textual.app import App
from textual.binding import Binding
from textual.reactive import reactive

from . import config
from .mock import MockSimulator, build_store
from .models import SessionStore, Status
from .providers import LiveProvider
from .screens import Dashboard, HelpScreen, ThemeScreen
from .sound import Alert
from .theme import BY_KEY, DEFAULT, PALETTES, colors, use

TICK_SECONDS = 0.5  # cadência das animações discretas e dos contadores

# A varredura de processos custa ~50 ms: roda em thread, a cada 2 s. No laço da
# UI ela engasgaria a animação; mais rápido que isso não muda nada na tela.
SCAN_SECONDS = 2.0

# Estados que merecem bip. READY é "terminou, é a sua vez" — o aviso que vale
# ouvir de outra janela. Para avisar também em INPUT/ERROR, é só incluí-los aqui.
ALERT_STATUSES = frozenset({Status.READY})

# Intervalo mínimo entre dois bips, em segundos.
ALERT_MIN_INTERVAL = 1.0


class WatchAIApp(App):
    TITLE = "WatchAI"
    SUB_TITLE = "session monitor"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("question_mark", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("b", "toggle_sound", "Bip"),
        Binding("t", "themes", "Themes"),
    ]

    # `tick` anima; `version` sobe a cada mudança de dados. Os widgets
    # observam os dois via `self.watch(self.app, ...)`.
    tick: reactive[int] = reactive(0)
    version: reactive[int] = reactive(0)
    sound_on: reactive[bool] = reactive(True)

    def __init__(
        self,
        seed: int | None = None,
        alert: Alert | None = None,
        theme_key: str | None = None,
        mock: bool = False,
        source=None,
    ) -> None:
        super().__init__()
        # A paleta precisa valer já no primeiro parse do TCSS, antes do on_mount.
        saved = theme_key if theme_key is not None else config.load_theme()
        self.palette_key = use(saved or DEFAULT.key).key
        if mock:
            self.store = build_store()
            self.simulator = MockSimulator(self.store, seed=seed)
            self.provider = None
        else:
            self.store = SessionStore()
            self.simulator = None
            self.provider = LiveProvider(self.store, source)
        self._scanning = False
        self._last_scan = 0.0
        self.alert = alert or Alert()
        # Estado visto por último, por sessão: é a diferença contra ele que
        # dispara o bip. Começa preenchido para uma sessão que já nasce READY
        # não tocar nada na abertura.
        self._seen: dict[int, Status] = {s.id: s.status for s in self.store.sessions}
        self._last_alert = 0.0

    def get_css_variables(self) -> dict[str, str]:
        # No primeiro parse o tema ainda é o do Textual, que não conhece os
        # $aw-*; injeta os da paleta ativa para o TCSS conseguir ser lido.
        return {**super().get_css_variables(), **colors().css_variables()}

    def on_mount(self) -> None:
        for palette in PALETTES:
            self.register_theme(palette.as_theme())
        self.theme = self.palette_key
        self.push_screen(Dashboard())
        self.set_interval(TICK_SECONDS, self._on_tick)
        if self.provider is not None:
            self.scan()

    # -- temas ------------------------------------------------------------------
    def apply_palette(self, key: str, *, remember: bool = False) -> None:
        """Troca a paleta agora. `remember=True` grava para as próximas sessões."""
        palette = BY_KEY.get(key, DEFAULT)
        self.palette_key = palette.key
        use(palette)
        self.theme = palette.key  # reescreve o TCSS com as novas variáveis
        self._repaint_all()
        if remember:
            config.save_theme(palette.key)

    def _repaint_all(self) -> None:
        """O TCSS se atualiza sozinho; quem desenha com Rich precisa repintar."""
        for screen in self.screen_stack:
            screen.refresh(layout=True)
            for widget in screen.walk_children():
                widget.refresh()

    def action_themes(self) -> None:
        if not isinstance(self.screen, ThemeScreen):
            self.push_screen(ThemeScreen())

    def _on_tick(self) -> None:
        if self.simulator is not None:
            if self.simulator.tick(datetime.now()):
                self.version += 1
        elif self.provider is not None and monotonic() - self._last_scan >= SCAN_SECONDS:
            self.scan()
        self.tick += 1

    # -- detecção real ----------------------------------------------------------
    def scan(self) -> None:
        """Dispara uma varredura, se já não houver uma em voo."""
        if self.provider is None or self._scanning:
            return
        self._scanning = True
        self._last_scan = monotonic()
        self.run_worker(self._scan_worker, thread=True, group="scan")

    def _scan_worker(self) -> None:
        """Thread: só lê o sistema. Quem mexe no store é a thread da UI."""
        try:
            snapshot = self.provider.read()
        except Exception:
            snapshot = None
        self.call_from_thread(self._scan_done, snapshot)

    def _scan_done(self, snapshot) -> None:
        self._scanning = False
        if snapshot is None:
            return
        if self.provider.apply(snapshot, datetime.now()):
            self.version += 1

    # -- bip --------------------------------------------------------------------
    def watch_version(self) -> None:
        """Toda mudança de dados passa por aqui — inclusive a integração real,
        que segundo o contrato do store também incrementa `version`."""
        self.check_alerts()

    def check_alerts(self) -> bool:
        """Compara com o estado visto antes e bipa se alguma sessão ficou READY.

        Um bip por rodada, mesmo que duas sessões mudem juntas.
        """
        entered = False
        for session in self.store.sessions:
            before = self._seen.get(session.id)
            if session.status is before:
                continue
            self._seen[session.id] = session.status
            if session.status in ALERT_STATUSES and before is not None:
                entered = True
        if entered and self.sound_on:
            self.play_alert()
        return entered

    def play_alert(self, *, force: bool = False) -> None:
        """Dispara o som sem segurar a UI (o processo morre sozinho em ~0,3 s).

        Rajadas de READY (segurar o R, por exemplo) viram um bip só: mais que
        isso é barulho e uma pilha de processos de áudio à toa.
        """
        now = monotonic()
        if not force and now - self._last_alert < ALERT_MIN_INTERVAL:
            return
        self._last_alert = now
        if self.alert.available:
            self.run_worker(self.alert.play(), group="alert", exclusive=False)
        else:
            self.bell()  # sem player no sistema: resta o bell do terminal

    def action_toggle_sound(self) -> None:
        self.sound_on = not self.sound_on
        if self.sound_on:
            self.play_alert(force=True)  # confirma ligando com o próprio som

    # -- ações globais -----------------------------------------------------------
    def action_help(self) -> None:
        if not isinstance(self.screen, HelpScreen):
            self.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        """R força a atualização agora: varredura na hora (ou, no mock, o próximo
        passo da simulação)."""
        if self.simulator is not None:
            self.simulator.step(datetime.now())
            self.version += 1
        else:
            self.scan()
