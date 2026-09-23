"""Dashboard principal: header · SESSIONS (cards ou lista) · EVENT STREAM · keybar.

Responsável por: layout responsivo, seleção, navegação por teclado, troca de
painel (TAB) e de visão (V).
"""

from __future__ import annotations

import asyncio

from textual.binding import Binding
from textual.containers import Grid, Vertical, VerticalScroll
from textual.widgets import Static
from textual.events import Resize
from textual.reactive import reactive
from textual.screen import Screen

from ..layout import CardMode, card_mode, Layout, layout_for, sessions_max_height
from ..widgets import (
    AppHeader,
    EventStream,
    KeyBar,
    ListHeader,
    PanelTitle,
    SessionCard,
    SessionRow,
)
from .details import DetailsScreen


# O que a área vazia diz, por causa. São três situações distintas e cada uma tem
# uma resposta própria — a última é a única em que não há nada errado.
VAZIO = {
    "sem-psutil": (
        "  psutil is missing — WatchAI cannot read the process table",
        "  install it:  pip install psutil   (or reinstall WatchAI)",
    ),
    "restrito": (
        "  cannot read the process table — only a handful of processes are visible",
        "  a sandbox (Snap, Flatpak), a container or hidepid is hiding the rest",
    ),
    "erro": (
        "  the process scan failed — the screen keeps the last reading",
        "  run with --mock to check whether the interface itself is fine",
    ),
    "": (
        "  no AI session detected",
        "  open claude, codex, gemini, opencode or aider in a terminal",
    ),
}


class Dashboard(Screen):
    BINDINGS = [
        Binding("up,k", "move('up')", "Up", show=False),
        Binding("down,j", "move('down')", "Down", show=False),
        Binding("left,h", "move('left')", "Left", show=False),
        Binding("right,l", "move('right')", "Right", show=False),
        Binding("enter", "open", "Open", show=False),
        Binding("tab", "toggle_panel", "Panel", show=False),
        Binding("v", "toggle_view", "View", show=False),
    ]

    selected: reactive[int] = reactive(0)
    panel: reactive[str] = reactive("sessions")  # "sessions" | "events"
    view: reactive[str] = reactive("cards")  # "cards" | "list"
    layout_mode: Layout = Layout.LARGE
    card_mode: CardMode = CardMode.FULL

    # -- composição ----------------------------------------------------------
    def compose(self):
        sessions = self.app.sessions_ordenadas()
        # A lista tem que ser gravada aqui, e não no on_mount: a primeira
        # varredura roda em thread e pode terminar entre os dois. Anotando no
        # on_mount, o dashboard registraria como "já desenhado" um conjunto de
        # sessões que o compose nunca chegou a montar — e a tela ficava vazia.
        self._ids = [s.id for s in sessions]
        yield AppHeader(id="header")
        yield PanelTitle(id="sessions-title")
        with VerticalScroll(id="sessions-area"):
            with Grid(id="cards"):
                for s in sessions:
                    yield SessionCard(s)
            with Vertical(id="rows"):
                yield ListHeader(id="list-header")
                for s in sessions:
                    yield SessionRow(s)
            yield Static("", id="empty")
        yield EventStream(id="events")
        yield KeyBar(id="keybar")

    def on_mount(self) -> None:
        # Duas varreduras seguidas não podem acertar os widgets ao mesmo tempo:
        # a segunda veria o DOM da primeira pela metade.
        self._reconcile_lock = asyncio.Lock()
        # Com detecção real as sessões nascem e morrem enquanto o app roda: os
        # widgets precisam acompanhar o store, não só o estado deles.
        self.watch(self.app, "version", lambda _: self.reconcile())
        self.reconcile()  # o store pode ter mudado entre o compose e agora
        self._sync_selection()
        self._apply_view()
        self._apply_empty()

    # -- sessões que entram e saem -------------------------------------------
    def reconcile(self) -> None:
        """Agenda o acerto dos widgets com o store."""
        ids = [s.id for s in self.app.sessions_ordenadas()]
        if ids == self._ids:
            return
        self._ids = ids
        self.run_worker(self._reconcile(), group="reconcile")

    async def _reconcile(self) -> None:
        """Tira só quem saiu e põe só quem entrou.

        Reconstruir tudo parecia mais simples, mas `remove()` no Textual é
        **assíncrono**: o widget só deixa o DOM depois. Remontar na mesma volta
        recriava `card-3` com o `card-3` antigo ainda lá, e o
        `DuplicateIds` matava o app — exatamente quando um agente abria ou
        fechava com outros na tela. Aqui a remoção é aguardada, e quem
        permanece nem é tocado (nada de piscar nem perder o scroll).
        """
        async with self._reconcile_lock:
            anteriores = self._cards()
            escolhida = (
                anteriores[self.selected].session.id
                if 0 <= self.selected < len(anteriores)
                else None
            )
            sessions = self.app.sessions_ordenadas()
            vivos = {s.id for s in sessions}
            cards = {c.session.id: c for c in self.query(SessionCard)}
            rows = {r.session.id: r for r in self.query(SessionRow)}

            for widget in [w for i, w in cards.items() if i not in vivos] + [
                w for i, w in rows.items() if i not in vivos
            ]:
                await widget.remove()

            novos_cards = [SessionCard(s) for s in sessions if s.id not in cards]
            novos_rows = [SessionRow(s) for s in sessions if s.id not in rows]
            if novos_cards:
                await self.query_one("#cards", Grid).mount_all(novos_cards)
            if novos_rows:
                await self.query_one("#rows", Vertical).mount_all(novos_rows)

            # A ordem do DOM tem que seguir a da lista: sem isto, ligar o `S`
            # reordenaria os dados e deixaria os widgets onde estavam.
            # `sort_children` reposiciona sem desmontar — remontar aqui é o que
            # já derrubou o app uma vez, com `DuplicateIds`.
            lugar = {s.id: i for i, s in enumerate(sessions)}
            fim = len(lugar)

            def posicao(widget) -> int:
                # O cabeçalho da lista não é sessão e fica sempre em cima.
                sessao = getattr(widget, "session", None)
                return -1 if sessao is None else lugar.get(sessao.id, fim)

            self.query_one("#cards", Grid).sort_children(key=posicao)
            self.query_one("#rows", Vertical).sort_children(key=posicao)
            # A seleção segue a **sessão**, não a posição: reordenar debaixo do
            # cursor não pode trocar qual card está selecionado.
            if escolhida is not None and escolhida in lugar:
                self.selected = lugar[escolhida]
            self.selected = max(0, min(self.selected, len(sessions) - 1))
            self._after_reconcile()

    def _after_reconcile(self) -> None:
        for card in self.query(SessionCard):
            card.mode = self.card_mode
        self._sync_selection()
        self._apply_empty()
        self._reveal_selected()

    def _apply_empty(self) -> None:
        """Sem nenhuma sessão, a área explica o que fazer em vez de ficar vazia.

        E explica **a causa certa**: uma lista vazia porque não há agente aberto
        e uma lista vazia porque não conseguimos ler a tabela de processos são
        situações diferentes, com respostas diferentes. Dizer a mesma frase nas
        duas faz quem caiu na segunda concluir que o app é quebrado.
        """
        vazio = self.query_one("#empty", Static)
        nenhuma = not self.app.store.sessions
        vazio.display = nenhuma
        if nenhuma:
            provider = getattr(self.app, "provider", None)
            causa = getattr(provider, "diagnostico", "") if provider else ""
            vazio.update("\n".join(VAZIO.get(causa, VAZIO[""])))
        self.query_one("#cards").display = self.view == "cards" and not nenhuma
        self.query_one("#rows").display = self.view == "list" and not nenhuma

    # -- responsividade ------------------------------------------------------
    def on_resize(self, event: Resize) -> None:
        width, height = event.size
        mode = layout_for(width)
        self.layout_mode = mode
        for m in Layout:
            self.set_class(m is mode, f"-{m.css}")
        self.query_one("#cards", Grid).styles.grid_size_columns = mode.columns
        # A área encolhe até o conteúdo (sem vão morto) mas nunca além deste teto,
        # senão ela empurraria o EVENT STREAM para fora da tela.
        teto = sessions_max_height(height)
        self.query_one("#sessions-area").styles.max_height = teto
        # O formato do card depende dos dois eixos: largura manda nas colunas,
        # altura manda no tamanho — um card mais alto que a área não aparece.
        self.card_mode = card_mode(width, teto)
        grade = self.query_one("#cards", Grid)
        # Sem caixa, os cards precisam de uma linha de respiro entre si — menos
        # no micro, onde o card é uma linha só e o respiro dobraria o custo.
        grade.styles.grid_gutter_vertical = 1 if self.card_mode is CardMode.COMPACT else 0
        for card in self.query(SessionCard):
            card.mode = self.card_mode
        self.call_after_refresh(self._reveal_selected)

    @property
    def columns(self) -> int:
        return 1 if self.view == "list" else self.layout_mode.columns

    # -- seleção ---------------------------------------------------------------
    def _cards(self) -> list[SessionCard]:
        return list(self.query(SessionCard))

    def _rows(self) -> list[SessionRow]:
        return list(self.query(SessionRow))

    def _sync_selection(self) -> None:
        for i, card in enumerate(self._cards()):
            card.selected = i == self.selected
        for i, row in enumerate(self._rows()):
            row.set_selected(i == self.selected)

    def _reveal_selected(self) -> None:
        widgets = self._cards() if self.view == "cards" else self._rows()
        if widgets and 0 <= self.selected < len(widgets):
            widgets[self.selected].scroll_visible(animate=False)

    def watch_selected(self) -> None:
        if self.is_mounted:
            self._sync_selection()
            self._reveal_selected()

    def select_session(self, session_id: int) -> None:
        for i, s in enumerate(self.app.store.sessions):
            if s.id == session_id:
                self.selected = i
                return

    def on_session_card_picked(self, message: SessionCard.Picked) -> None:
        self.panel = "sessions"
        self.select_session(message.session_id)
        if message.open:
            self.action_open()

    # -- view / panel ---------------------------------------------------------
    def _apply_view(self) -> None:
        nenhuma = not self.app.store.sessions
        self.query_one("#cards").display = self.view == "cards" and not nenhuma
        self.query_one("#rows").display = self.view == "list" and not nenhuma
        self.query_one("#sessions-title", PanelTitle).view = self.view
        self.call_after_refresh(self._reveal_selected)

    def watch_view(self) -> None:
        if self.is_mounted:
            self._apply_view()

    def watch_panel(self, panel: str) -> None:
        if self.is_mounted:
            self.query_one("#sessions-title", PanelTitle).focused_panel = panel == "sessions"
            self.query_one("#events", EventStream).focused_panel = panel == "events"

    # -- ações ----------------------------------------------------------------
    def action_toggle_view(self) -> None:
        self.view = "list" if self.view == "cards" else "cards"

    def action_toggle_panel(self) -> None:
        self.panel = "events" if self.panel == "sessions" else "sessions"

    def action_open(self) -> None:
        if self.panel != "sessions":
            return
        sessions = self.app.store.sessions
        # A seleção pode estar velha por um instante: entre a varredura mexer no
        # store e os widgets acertarem, uma tecla cabe no meio.
        if 0 <= self.selected < len(sessions):
            self.app.push_screen(DetailsScreen(sessions[self.selected].id))

    def action_move(self, direction: str) -> None:
        if self.panel == "events":
            if direction in ("up", "down"):
                self.query_one("#events", EventStream).scroll_events(-1 if direction == "up" else 1)
            return

        n = len(self.app.store.sessions)
        cols = self.columns
        i = self.selected
        if direction in ("left", "right"):
            if cols == 1:
                return  # ← → só fazem sentido com várias colunas
            i += -1 if direction == "left" else 1
        elif direction == "up":
            i -= cols
        else:  # down
            j = i + cols
            if j >= n and (i // cols) < ((n - 1) // cols):
                j = n - 1  # última linha incompleta: cai no último card
            i = j
        if 0 <= i < n:
            self.selected = i
