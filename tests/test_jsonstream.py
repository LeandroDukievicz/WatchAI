"""Contrato público da saída NDJSON usada por integrações."""

from __future__ import annotations

import io
import json
from datetime import datetime

import pytest

from watchai.__main__ import parse
from watchai.jsonstream import SCHEMA_VERSION, stream
from watchai.models import SessionStore
from watchai.providers import LiveProvider, ProcObs, Snapshot, TermObs


class Source:
    def snapshot(self):
        created = datetime.now().timestamp() - 60
        agent = ProcObs(
            pid=42,
            kind="claude",
            label="claude",
            terminal="pid:7:1",
            terminal_label="pwsh #7",
            terminal_started=created - 30,
            created=created,
            cpu=0.0,
            cwd="/workspace/demo",
            terminal_pid=7,
        )
        return Snapshot(
            agents=(agent,),
            terminals={agent.terminal: TermObs(agent.terminal, agent.terminal_label, created - 30)},
        )


class NoTranscripts:
    def atribuir(self, kind, agents):
        return {pid: None for pid, _, _ in agents}


def test_json_once_e_um_documento_completo_por_linha():
    output = io.StringIO()
    monitor = LiveProvider(SessionStore(), Source(), transcripts=NoTranscripts())

    assert stream(output, once=True, provider=monitor) == 0
    lines = output.getvalue().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["diagnostic"] is None and data["active"] == 1
    assert data["counts"]["ready"] == 1
    session = data["sessions"][0]
    assert session["terminal_pid"] == 7
    assert session["agents"][0]["kind"] == "claude"
    assert session["status"] == "ready"


def test_once_so_existe_no_modo_json():
    assert parse(["--json", "--once"]).json
    with pytest.raises(SystemExit):
        parse(["--once"])
    with pytest.raises(SystemExit):
        parse(["--json", "--mock"])
