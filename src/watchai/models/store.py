"""Armazém em memória das sessões e do event stream.

Na fase de integração real, é este objeto que será alimentado pelo
descobridor de processos / hooks. A UI só lê daqui.
"""

from __future__ import annotations

from datetime import datetime

from .session import Session, SessionEvent, Status

MAX_EVENTS = 200


class SessionStore:
    def __init__(self, sessions: list[Session] | None = None) -> None:
        self.sessions: list[Session] = sessions or []
        self.events: list[SessionEvent] = []  # mais novo primeiro

    # -- consultas ---------------------------------------------------------
    def get(self, session_id: int) -> Session | None:
        return next((s for s in self.sessions if s.id == session_id), None)

    def counts(self) -> dict[Status, int]:
        out = {s: 0 for s in Status}
        for session in self.sessions:
            out[session.status] += 1
        return out

    @property
    def active(self) -> int:
        return sum(1 for s in self.sessions if s.online)

    def events_for(self, session_id: int, limit: int = 5) -> list[SessionEvent]:
        return [e for e in self.events if e.session_id == session_id][:limit]

    # -- escrita -----------------------------------------------------------
    def log(self, session: Session, at: datetime, message: str | None = None) -> None:
        self.events.insert(
            0,
            SessionEvent(
                at=at,
                session_id=session.id,
                short=session.short,
                status=session.status,
                message=message or session.activity,
            ),
        )
        del self.events[MAX_EVENTS:]

    def transition(
        self, session: Session, status: Status, activity: str, at: datetime
    ) -> None:
        if status is not session.status:
            session.status_since = at
        if status is Status.STARTING:
            session.started_at = at
        session.status = status
        session.activity = activity
        self.log(session, at)
