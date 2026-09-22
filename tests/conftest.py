"""A suíte não faz barulho.

A simulação entra em READY dezenas de vezes durante os testes; sem isto, rodar
`pytest` dispararia áudio de verdade a cada vez. Quem testa o bip injeta um
`Alert` falso e conta as chamadas.
"""

from __future__ import annotations

import pytest

from watchai import sound


@pytest.fixture(autouse=True)
def sem_audio(monkeypatch):
    monkeypatch.setattr(sound, "find_player", lambda: None)
