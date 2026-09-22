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

from . import config, sound
from .focus import Focuser
from .mock import MockSimulator, build_store
from .models import PRIORIDADE, SessionStore, Status
from .notify import Notifier
from .providers import LiveProvider
from .screens import Dashboard, DetailsScreen, HelpScreen, ThemeScreen
from .sound import Alert
from .theme import BY_KEY, DEFAULT, PALETTES, colors, use

TICK_SECONDS = 0.5  # cadência das animações discretas e dos contadores

# A varredura de processos custa ~50 ms: roda em thread, a cada 2 s. No laço da
# UI ela engasgaria a animação; mais rápido que isso não muda nada na tela.
SCAN_SECONDS = 2.0

# Estados que merecem aviso, e o timbre de cada um. São os três que param o
# seu trabalho: terminou, travou esperando você, quebrou. Timbres diferentes
# porque avisar os três com o mesmo som obriga a olhar para saber qual foi.
ALERT_SOUND = {
    Status.READY: sound.READY,
    Status.INPUT: sound.INPUT,
    Status.ERROR: sound.ERROR,
}
ALERT_STATUSES = frozenset(ALERT_SOUND)

# Intervalo mínimo entre dois bips **do mesmo timbre**, em segundos. Uma
# rajada de READY vira um bip só; mas um READY seguido de um ERROR são duas
# notícias diferentes e as duas têm que ser ouvidas.
ALERT_MIN_INTERVAL = 1.0

# Teto de notificações por rodada: cinco sessões mudando juntas não podem virar
# cinco pop-ups.
MAX_NOTIFICACOES = 3


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
        Binding("n", "toggle_notify", "Notify"),
        Binding("A", "goto", "Go to window"),
    ]

    # `tick` anima; `version` sobe a cada mudança de dados. Os widgets
    # observam os dois via `self.watch(self.app, ...)`.
    tick: reactive[int] = reactive(0)
    version: reactive[int] = reactive(0)
    sound_on: reactive[bool] = reactive(True)
    # A notificação do sistema nasce desligada: é intrusiva, e quem liga é você.
    notify_on: reactive[bool] = reactive(False)

    def __init__(
        self,
        seed: int | None = None,
        alert: Alert | None = None,
        theme_key: str | None = None,
        mock: bool = False,
        source=None,
        notifier: Notifier | None = None,
        focuser: Focuser | None = None,
    ) -> None:
        super().__init__()
        # A paleta precisa valer já no primeiro parse do TCSS, antes do on_mount.
        saved = theme_key if theme_key is not None else config.load_theme()
        self.palette_key = use(saved or DEFAULT.key).key
        self.set_reactive(WatchAIApp.sound_on, config.load_alerts())
        self.set_reactive(WatchAIApp.notify_on, config.load_notify())
        if mock:
            self.store = build_store()
            self.simulator = MockSimulator(self.store, seed=seed)
            self.provider = None
        else:
            self.store = SessionStore()
            self.simulator = None
            self.provider = LiveProvider(self.store, source)
            # O que aconteceu enquanto o app estava fechado continua valendo:
            # o stream abre com o histórico da execução anterior.
            self.store.load_events(config.load_events())
        self._scanning = False
        self._last_scan = 0.0
        self.alert = alert or Alert()
        self.notifier = notifier if notifier is not None else Notifier()
        self.focuser = focuser if focuser is not None else Focuser()
        # O terminal avisa quando ganha e perde foco. Começamos assumindo que
        # não está em foco: notificar à toa incomoda menos que ficar mudo.
        self._focused = False
        # Estado visto por último, por sessão: é a diferença contra ele que
        # dispara o bip. Começa preenchido para uma sessão que já nasce READY
        # não tocar nada na abertura.
        self._seen: dict[int, Status] = {s.id: s.status for s in self.store.sessions}
        self._last_alert: dict[str, float] = {}

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

    def on_unmount(self) -> None:
        self.save_history()

    def save_history(self) -> None:
        if self.provider is not None:  # o mock não tem histórico que valha salvar
            config.save_events(self.store.dump_events())

    # -- foco do terminal --------------------------------------------------------
    def on_app_focus(self) -> None:
        self._focused = True

    def on_app_blur(self) -> None:
        self._focused = False

    # -- bip --------------------------------------------------------------------
    def watch_version(self) -> None:
        """Toda mudança de dados passa por aqui — inclusive a integração real,
        que segundo o contrato do store também incrementa `version`."""
        self.check_alerts()

    def check_alerts(self) -> bool:
        """Compara com o estado visto antes e avisa o que passou a pedir você.

        Um bip por rodada, mesmo que duas sessões mudem juntas: o timbre é o do
        estado mais urgente da rodada.
        """
        disparos = []
        for session in self.store.sessions:
            before = self._seen.get(session.id)
            if session.status is before:
                continue
            self._seen[session.id] = session.status
            # `before is None` é sessão recém-descoberta: o inventário da
            # abertura não avisa nada.
            if session.status in ALERT_STATUSES and before is not None:
                disparos.append(session)
        if not disparos or not self.sound_on:
            return bool(disparos)

        principal = min(disparos, key=lambda s: PRIORIDADE.index(s.status))
        self.play_alert(kind=ALERT_SOUND[principal.status])
        for session in disparos[:MAX_NOTIFICACOES]:
            self.notify_session(session)
        return True

    def notify_session(self, session) -> None:
        """Notificação do sistema — só quando você NÃO está olhando o WatchAI."""
        if not self.notify_on or self._focused or not self.notifier.available:
            return
        title = f"{session.status.label} · {session.short}"
        body = session.activity or ""
        if session.terminal:
            body = f"{body}  ({session.terminal})" if body else session.terminal
        self.run_worker(
            self.notifier.send(title, body, ALERT_SOUND.get(session.status, sound.READY)),
            group="notify",
            exclusive=False,
        )

    def play_alert(self, kind: str = sound.READY, *, force: bool = False) -> None:
        """Dispara o som sem segurar a UI (o processo morre sozinho em ~0,3 s).

        Rajadas de READY (segurar o R, por exemplo) viram um bip só: mais que
        isso é barulho e uma pilha de processos de áudio à toa.
        """
        now = monotonic()
        if not force and now - self._last_alert.get(kind, 0.0) < ALERT_MIN_INTERVAL:
            return
        self._last_alert[kind] = now
        if self.alert.available:
            self.run_worker(self.alert.play(kind), group="alert", exclusive=False)
        else:
            self.bell()  # sem player no sistema: resta o bell do terminal

    # -- ir para a janela da sessão ----------------------------------------------
    def selected_session(self):
        """A sessão em foco agora — no dashboard ou dentro dos detalhes."""
        tela = self.screen
        if isinstance(tela, DetailsScreen):
            return self.store.get(tela.session_id)
        indice = getattr(tela, "selected", None)
        if indice is None:
            return None
        sessions = self.store.sessions
        return sessions[indice] if 0 <= indice < len(sessions) else None

    def action_goto(self) -> None:
        """`G` põe na frente a janela do terminal onde a sessão roda."""
        session = self.selected_session()
        if session is None:
            return
        self.run_worker(self._goto(session), group="goto", exclusive=True)

    async def _goto(self, session) -> None:
        resultado = await self.focuser.focus(
            pid=session.window_pid,
            app=session.window_app,
            tty=session.tty,
            title=session.project or session.name,
        )
        self.notify(f"{session.short}: {resultado}", timeout=4)

    def action_toggle_notify(self) -> None:
        """`N` liga e desliga a notificação do sistema, sem mexer no bip."""
        self.notify_on = not self.notify_on
        config.save_notify(self.notify_on)
        estado = "ligadas" if self.notify_on else "desligadas"
        self.notify(f"notificações {estado}", timeout=3)

    def action_toggle_sound(self) -> None:
        """`B` liga e desliga o bip, e a escolha vale para as próximas
        execuções. A notificação tem interruptor próprio (`N`)."""
        self.sound_on = not self.sound_on
        config.save_alerts(self.sound_on)
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
