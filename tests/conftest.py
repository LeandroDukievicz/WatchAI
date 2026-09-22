"""A suíte não faz barulho, não lê e não escreve a config do usuário.

A simulação entra em READY dezenas de vezes durante os testes; sem isto, rodar
`pytest` dispararia áudio de verdade a cada vez. Quem testa o bip injeta um
`Alert` falso e conta as chamadas.

A paleta ativa e o arquivo de configuração são globais ao processo: cada teste
recebe os dois zerados, para não depender do tema que o usuário escolheu nem
sobrescrever a escolha dele ao rodar a suíte.
"""

from __future__ import annotations

import pytest

from watchai import sound, theme


@pytest.fixture(autouse=True)
def sem_audio(monkeypatch):
    monkeypatch.setattr(sound, "find_player", lambda: None)


@pytest.fixture(autouse=True)
def config_isolada(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


@pytest.fixture(autouse=True)
def paleta_padrao():
    theme.use(theme.DEFAULT)
    yield
    theme.use(theme.DEFAULT)
