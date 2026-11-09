"""Integração pequena com o sistema real, executada nos três runners do CI."""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

from watchai.providers import PsutilSource


def test_psutil_encontra_agente_real_e_identifica_o_terminal(tmp_path):
    """Passa pela tabela de processos real, não por uma imitação injetada."""
    fake_cli = tmp_path / "claude"
    fake_cli.write_text("import time\ntime.sleep(20)\n", encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(fake_cli)])
    try:
        found = None
        last = None
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            last = PsutilSource().snapshot()
            found = next(
                (agent for agent in last.agents if agent.pid == process.pid),
                None,
            )
            if found is not None:
                break
            time.sleep(0.2)
        assert found is not None, f"diagnostic={last.diagnostico if last else 'no snapshot'}"
        assert found.kind == "claude"
        assert found.terminal and found.terminal_label
        if sys.platform == "win32":
            assert found.terminal.startswith("pid:")
            assert found.terminal_pid is not None
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.mark.skipif(sys.platform != "win32", reason="WinRT só existe no Windows")
def test_os_tipos_do_toast_carregam_no_windows():
    from watchai.notify import TOAST_TYPES_PS

    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", TOAST_TYPES_PS],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
