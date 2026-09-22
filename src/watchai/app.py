"""WatchAI — protótipo visual (dados mockados).

Este app NÃO detecta processos nem integra com nenhuma IA. Tudo que aparece
vem de `watchai.mock`. A camada visual já consome um `SessionStore`, então a
integração real futura só precisa alimentar o mesmo store.
"""

from __future__ import annotations

from datetime import datetime
from time import monotonic

from textual.app import App
from textual.binding import Binding
from textual.reactive import reactive

from .mock import MockSimulator, build_store
from .models import Status
from .screens import Dashboard, HelpScreen
from .sound import Alert
from .theme import AI_WATCH_THEME

TICK_SECONDS = 0.5  # cadência das animações discretas e dos contadores

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
    ]

    # `tick` anima; `version` sobe a cada mudança de dados. Os widgets
    # observam os dois via `self.watch(self.app, ...)`.
    tick: reactive[int] = reactive(0)
    version: reactive[int] = reactive(0)
    sound_on: reactive[bool] = reactive(True)

    def __init__(self, seed: int | None = None, alert: Alert | None = None) -> None:
        super().__init__()
        self.store = build_store()
        self.simulator = MockSimulator(self.store, seed=seed)
        self.alert = alert or Alert()
        # Estado visto por último, por sessão: é a diferença contra ele que
        # dispara o bip. Começa preenchido para uma sessão que já nasce READY
        # não tocar nada na abertura.
        self._seen: dict[int, Status] = {s.id: s.status for s in self.store.sessions}
        self._last_alert = 0.0

    def get_css_variables(self) -> dict[str, str]:
        # As variáveis $aw-* precisam existir já no primeiro parse do TCSS.
        return {**super().get_css_variables(), **AI_WATCH_THEME.variables}

    def on_mount(self) -> None:
        self.register_theme(AI_WATCH_THEME)
        self.theme = "watchai"
        self.push_screen(Dashboard())
        self.set_interval(TICK_SECONDS, self._on_tick)

    def _on_tick(self) -> None:
        if self.simulator.tick(datetime.now()):
            self.version += 1
        self.tick += 1

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
        """No protótipo, R avança a simulação imediatamente."""
        self.simulator.step(datetime.now())
        self.version += 1
