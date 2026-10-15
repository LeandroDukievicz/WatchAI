"""Onde fica a casa do usuário — inclusive quando o programa está confinado.

Num snap **strict** o `HOME` não é a sua casa: o snapd aponta para a pasta
privada do pacote (`~/snap/watchai/current`), e é lá que `Path.home()` cai. Os
diários que o WatchAI lê moram na casa de verdade, e é o snapd mesmo que
entrega o caminho dela em `SNAP_REAL_HOME`.

Sem isto, o app confinado não acha diário nenhum: todo card cai nos sinais de
processo, o projeto some do título e o estado vira palpite. O programa roda e
mente — pior que não rodar.

A regra de qual casa usar é simples, e as duas aparecem:

- **ler o que é do usuário** (`~/.claude`, `~/.codex`, encurtar caminho para
  `~`): casa de verdade, via `casa_do_usuario()`;
- **escrever o que é nosso** (tema, histórico, o recado da statusline): a casa
  confinada, que é `Path.home()` e já é gravável sem pedir permissão nenhuma à
  loja. Por isso `config.py` **não** usa este módulo.
"""

from __future__ import annotations

import os
from pathlib import Path


def casa_do_usuario() -> Path:
    """A casa do usuário, não a que o confinamento inventou.

    Fora de um snap, `SNAP_REAL_HOME` não existe e isto é `Path.home()`.
    """
    real = os.environ.get("SNAP_REAL_HOME")
    if real:
        return Path(real)
    return Path.home()


def confinado() -> bool:
    """Estamos rodando dentro de um snap?

    `SNAP` é posto pelo snapd e aponta para a raiz do pacote montado. Serve
    para o programa explicar o que não vai conseguir fazer ali dentro, em vez
    de falhar com um erro de permissão que não diz nada.
    """
    return bool(os.environ.get("SNAP"))


__all__ = ["casa_do_usuario", "confinado"]
