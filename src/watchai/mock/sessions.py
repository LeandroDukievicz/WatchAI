"""Dados SIMULADOS. Nada aqui detecta processos reais.

`build_store()` cria 6 sessões (uma em cada estado principal) e um histórico
de eventos plausível. `MockSimulator` muda o estado de uma sessão aleatória
a cada 5–12 s, só para avaliarmos a interface em movimento.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from ..models import Session, SessionStore, Status

S = timedelta(seconds=1)

# (status, peso) — transições plausíveis a partir de cada estado
TRANSITIONS: dict[Status, list[tuple[Status, int]]] = {
    Status.WORKING: [
        (Status.READY, 40),
        (Status.INPUT, 18),
        (Status.WAITING, 16),
        (Status.ERROR, 8),
        (Status.WORKING, 18),  # mesma etapa, outra atividade
    ],
    Status.READY: [(Status.WORKING, 80), (Status.OFFLINE, 20)],
    Status.WAITING: [(Status.WORKING, 65), (Status.INPUT, 20), (Status.ERROR, 15)],
    Status.INPUT: [(Status.WORKING, 88), (Status.ERROR, 12)],
    Status.ERROR: [(Status.WORKING, 45), (Status.OFFLINE, 35), (Status.READY, 20)],
    Status.OFFLINE: [(Status.STARTING, 100)],
    Status.STARTING: [(Status.WORKING, 70), (Status.READY, 30)],
}

ACTIVITIES: dict[Status, list[str]] = {
    Status.WORKING: [
        "generating code",
        "editing files",
        "running tests",
        "reading repository",
        "refactoring modules",
        "installing dependencies",
        "applying patch",
    ],
    Status.READY: ["task completed", "changes applied", "awaiting next prompt"],
    Status.WAITING: [
        "waiting for build",
        "waiting for API response",
        "waiting for test runner",
    ],
    Status.INPUT: [
        "waiting for confirmation",
        "approval needed to run command",
        "asking a question",
    ],
    Status.ERROR: [
        "test suite failed (exit 1)",
        "rate limit exceeded",
        "tool call failed",
    ],
    Status.OFFLINE: ["process terminated", "process stopped"],
    Status.STARTING: ["booting agent", "loading context"],
}


def build_store(now: datetime | None = None) -> SessionStore:
    now = now or datetime.now()

    def mk(
        id: int,
        name: str,
        short: str,
        status: Status,
        project: str,
        pid: int,
        started: int,
        since: int,
        activity: str,
    ) -> Session:
        return Session(
            id=id,
            name=name,
            short=short,
            status=status,
            project=project,
            directory=f"~/{project}",
            pid=pid,
            started_at=now - started * S,
            status_since=now - since * S,
            activity=activity,
        )

    sessions = [
        mk(3, "CLAUDE CODE", "CLAUDE", Status.WORKING, "telegram-downloader",
           184372, 12 * 60 + 44, 4 * 60 + 12, "generating telegram_downloader.py"),
        mk(1, "CODEX", "CODEX", Status.READY, "dukie-tech",
           171905, 17 * 60 + 44, 1 * 60 + 42, "task completed"),
        mk(2, "GEMINI", "GEMINI", Status.WAITING, "research-agent",
           190114, 9 * 60 + 20, 3 * 60 + 11, "waiting for API response"),
        mk(4, "OPENCODE", "OPENCODE", Status.INPUT, "devleandro",
           195560, 6 * 60 + 5, 27, "waiting for confirmation"),
        mk(5, "AIDER", "AIDER", Status.ERROR, "devsaderiva",
           168821, 22 * 60 + 30, 2 * 60 + 51, "test suite failed (exit 1)"),
        mk(6, "COPILOT", "COPILOT", Status.OFFLINE, "yt-downloader",
           0, 0, 8 * 60, "process terminated"),
    ]
    store = SessionStore(sessions)

    # Histórico: eventos anteriores por sessão (o mais novo é o estado atual).
    older = {
        3: [("user prompt", Status.WORKING, 4 * 60 + 48),
            ("command executed", Status.WORKING, 4 * 60 + 33),
            ("reading repository", Status.WORKING, 4 * 60 + 20)],
        1: [("user prompt", Status.WORKING, 9 * 60 + 10),
            ("running tests", Status.WORKING, 4 * 60 + 5),
            ("applying patch", Status.WORKING, 2 * 60 + 30)],
        2: [("user prompt", Status.WORKING, 6 * 60),
            ("reading repository", Status.WORKING, 4 * 60 + 40)],
        4: [("user prompt", Status.WORKING, 3 * 60),
            ("editing files", Status.WORKING, 1 * 60 + 20)],
        5: [("user prompt", Status.WORKING, 7 * 60),
            ("running tests", Status.WORKING, 3 * 60 + 40)],
        6: [("user prompt", Status.WORKING, 20 * 60),
            ("task completed", Status.READY, 12 * 60)],
    }
    events = []
    for s in sessions:
        events.append((s.status_since, s, s.status, s.activity))
        for msg, st, ago in older[s.id]:
            events.append((now - ago * S, s, st, msg))
    for at, s, st, msg in sorted(events, key=lambda e: e[0]):
        keep = s.status
        s.status = st  # log() usa o status da sessão
        store.log(s, at, msg)
        s.status = keep
    return store


class MockSimulator:
    """Muda o estado de uma sessão aleatória a cada 5–12 s."""

    def __init__(self, store: SessionStore, seed: int | None = None) -> None:
        self.store = store
        self.rng = random.Random(seed)
        self.next_at = datetime.now() + self._delay()

    def _delay(self) -> timedelta:
        return self.rng.uniform(5, 12) * S

    def _pick(self, options: list[tuple[Status, int]]) -> Status:
        statuses, weights = zip(*options)
        return self.rng.choices(statuses, weights=weights, k=1)[0]

    def step(self, now: datetime) -> Session:
        """Avança UMA sessão aleatória e devolve-a."""
        session = self.rng.choice(self.store.sessions)
        new = self._pick(TRANSITIONS[session.status])
        activity = self.rng.choice(ACTIVITIES[new])
        self.store.transition(session, new, activity, now)
        if new is Status.STARTING:
            session.pid = self.rng.randint(150_000, 210_000)
        if new is Status.OFFLINE:
            session.pid = 0
        self.next_at = now + self._delay()
        return session

    def settle(self, now: datetime) -> bool:
        """STARTING é transitório: resolve após ~4 s."""
        changed = False
        for s in self.store.sessions:
            if s.status is Status.STARTING and (now - s.status_since) >= 4 * S:
                new = self._pick(TRANSITIONS[Status.STARTING])
                self.store.transition(s, new, self.rng.choice(ACTIVITIES[new]), now)
                changed = True
        return changed

    def tick(self, now: datetime) -> bool:
        """Chamado pelo app a cada tick. True se algo mudou."""
        changed = self.settle(now)
        if now >= self.next_at:
            self.step(now)
            changed = True
        return changed
