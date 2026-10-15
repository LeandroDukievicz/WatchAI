"""A casa do usuário quando o programa está confinado.

Num snap strict o `HOME` é a pasta privada do pacote, e `Path.home()` cai lá.
Os diários moram na casa de verdade. Estes testes guardam a diferença, que é
invisível fora do snap e fatal dentro dele: sem ela o app roda, não acha
diário nenhum e passa a chutar o estado de toda sessão.
"""

from __future__ import annotations

import json
from pathlib import Path

from watchai.paths import casa_do_usuario, confinado
from watchai.providers.limits import Limites
from watchai.providers.transcript import Transcripts


def test_fora_do_snap_a_casa_e_a_de_sempre(monkeypatch):
    monkeypatch.delenv("SNAP_REAL_HOME", raising=False)
    monkeypatch.delenv("SNAP", raising=False)
    assert casa_do_usuario() == Path.home()
    assert confinado() is False


def test_dentro_do_snap_a_casa_e_a_de_verdade(monkeypatch, tmp_path):
    # é o snapd que põe as duas: SNAP aponta para o pacote montado e
    # SNAP_REAL_HOME para a casa que o confinamento escondeu
    monkeypatch.setenv("SNAP", "/snap/watchai/42")
    monkeypatch.setenv("SNAP_REAL_HOME", str(tmp_path))
    assert casa_do_usuario() == tmp_path
    assert confinado() is True


def test_o_leitor_de_diarios_procura_na_casa_de_verdade(monkeypatch, tmp_path):
    """O erro que isto impede: `Transcripts()` sem argumento ia para a pasta
    privada do snap, onde nunca houve diário de agente nenhum."""
    confinada = tmp_path / "snap" / "watchai" / "current"
    confinada.mkdir(parents=True)
    verdadeira = tmp_path / "casa"
    (verdadeira / ".claude" / "projects").mkdir(parents=True)

    monkeypatch.setenv("HOME", str(confinada))
    monkeypatch.setenv("SNAP", "/snap/watchai/42")
    monkeypatch.setenv("SNAP_REAL_HOME", str(verdadeira))

    assert Transcripts().leitores["claude"].raiz == verdadeira / ".claude" / "projects"
    assert Limites().leitores[0].raiz == verdadeira / ".codex" / "sessions"


def test_a_statusline_mira_o_claude_code_da_casa_de_verdade(monkeypatch, tmp_path):
    from watchai import statusline

    confinada = tmp_path / "confinada"
    confinada.mkdir()
    monkeypatch.setenv("HOME", str(confinada))
    monkeypatch.setenv("SNAP", "/snap/watchai/42")
    monkeypatch.setenv("SNAP_REAL_HOME", str(tmp_path / "casa"))

    # sem ~/.claude na casa de verdade, o recado tem de citar **essa** casa
    resultado = statusline.instalar()
    assert not resultado.ok
    assert str(tmp_path / "casa") in resultado.mensagem


def test_no_snap_a_falha_de_escrita_explica_o_porque(monkeypatch, tmp_path):
    """Dentro do snap o ~/.claude é lido e não escrito — de propósito. O
    programa entrega a linha pronta em vez de um erro de permissão mudo."""
    from watchai import statusline

    casa = tmp_path / "casa" / ".claude"
    casa.mkdir(parents=True)
    (casa / "settings.json").write_text(json.dumps({}), encoding="utf-8")

    monkeypatch.setenv("SNAP", "/snap/watchai/42")
    monkeypatch.setenv("SNAP_REAL_HOME", str(tmp_path / "casa"))

    def recusa(*_a, **_k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(statusline, "_gravar", recusa)
    resultado = statusline.instalar(base=casa)
    assert not resultado.ok
    assert "não escreve nele" in resultado.mensagem
    assert "pipx install watchai" in resultado.mensagem
