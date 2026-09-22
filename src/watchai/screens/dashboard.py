"""Dashboard principal: header · SESSIONS (cards ou lista) · EVENT STREAM · keybar.

Responsável por: layout responsivo, seleção, navegação por teclado, troca de
painel (TAB) e de visão (V).
"""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Grid, Vertical, VerticalScroll
from textual.events import Resize
from textual.reactive import reactive
from textual.screen import Screen

from ..layout import Layout, layout_for, sessions_max_height
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

    # -- composição ----------------------------------------------------------
    def compose(self):
        sessions = self.app.store.sessions
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
        yield EventStream(id="events")
        yield KeyBar(id="keybar")

    def on_mount(self) -> None:
        self._sync_selection()
        self._apply_view()

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
        self.query_one("#sessions-area").styles.max_height = sessions_max_height(height)
        for card in self.query(SessionCard):
            card.compact = mode.compact
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
        self.query_one("#cards").display = self.view == "cards"
        self.query_one("#rows").display = self.view == "list"
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
        if sessions:
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
