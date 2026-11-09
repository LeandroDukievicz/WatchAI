"""Saída NDJSON para integrações sem duplicar a detecção do WatchAI.

Cada linha é um retrato completo e independente. Isso deixa a saída útil tanto
para processos longos (extensão do VS Code, waybar) quanto para scripts que
leem apenas a primeira linha com ``watchai --json --once``.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import TextIO

from .models import Session, SessionStore, Status
from .providers import LiveProvider

SCHEMA_VERSION = 1
INTERVAL_SECONDS = 2.0


def _date(value: datetime) -> str:
    """ISO-8601 inequívoco, inclusive para datetimes locais sem timezone."""
    return value.astimezone().isoformat(timespec="milliseconds")


def _session(session: Session) -> dict:
    return {
        "id": session.id,
        "key": session.key,
        "name": session.name,
        "short": session.short,
        "status": session.status.name.lower(),
        "attention": session.status.attention,
        "activity": session.activity,
        "project": session.project,
        "directory": session.directory,
        "pid": session.pid,
        "terminal": session.terminal,
        "terminal_pid": session.terminal_pid,
        "tty": session.tty or None,
        "window_pid": session.window_pid,
        "window_app": session.window_app or None,
        "started_at": _date(session.started_at),
        "status_since": _date(session.status_since),
        "online": session.online,
        "agents": [
            {
                "pid": agent.pid,
                "kind": agent.kind,
                "label": agent.label,
                "status": agent.status.name.lower(),
                "attention": agent.status.attention,
                "activity": agent.activity,
                "started_at": _date(agent.started_at),
                "status_since": _date(agent.status_since),
            }
            for agent in session.agents
        ],
    }


def snapshot(provider: LiveProvider, store: SessionStore, now: datetime | None = None) -> dict:
    """Lê uma vez e devolve um documento JSON serializável."""
    instant = now or datetime.now()
    provider.poll(instant)
    counts = store.counts()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "diagnostic": provider.diagnostico or None,
        "active": store.active,
        "counts": {status.name.lower(): counts[status] for status in Status},
        "sessions": [_session(session) for session in store.sessions],
    }


def stream(
    output: TextIO,
    *,
    once: bool = False,
    interval: float = INTERVAL_SECONDS,
    provider: LiveProvider | None = None,
) -> int:
    """Emite um retrato por linha até interrupção; nunca mistura logs no stdout."""
    monitor = provider or LiveProvider(SessionStore())
    store = monitor.store
    try:
        while True:
            document = snapshot(monitor, store)
            output.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")
            output.flush()
            if once:
                return 0
            time.sleep(max(0.1, interval))
    except (BrokenPipeError, KeyboardInterrupt):
        return 0


__all__ = ["INTERVAL_SECONDS", "SCHEMA_VERSION", "snapshot", "stream"]
