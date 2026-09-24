"""O nome que a janela do terminal mostra enquanto o WatchAI roda.

Aberto pelo ícone da área de trabalho, o terminal nasce com o nome que o
emulador deu a si mesmo — "Terminal" no GNOME. Chamado num terminal já aberto,
o nome é o que o shell escreveu por último (`usuário@host: ~/projeto`). Nos
dois casos nada na janela, no alt-tab ou na barra de tarefas diz que ali está o
WatchAI, e é isto que este módulo resolve: quem manda no título é quem está
rodando na tty, e um OSC na saída padrão o troca.

É o mesmo canal que o `⇧A` já usa para marcar a janela das outras sessões
(`focus.set_title`); o que muda é o destino — lá é a tty do agente, aqui é a
nossa própria saída.

Na saída devolvemos o título de antes pela **pilha de títulos** do terminal
(XTWINOPS `22;0t` / `23;0t`). Guardá-lo em variável exigiria perguntá-lo ao
terminal, e a consulta (OSC 21) quase ninguém responde — além de obrigar a ler
a entrada, que a essa altura é do Textual. Terminal que não conhece a pilha
ignora as duas sequências e fica com "WatchAI" até o shell reescrever o título
no próximo prompt, que é o que bash e zsh já fazem sozinhos.

Dentro do tmux o OSC chega ao **painel**, não à janela do emulador: o título
externo ali é do tmux, que só o repassa com `set-titles on`. Renomear a janela
do tmux por conta própria seria mexer na sessão de quem chamou, e por isso não
é feito.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

TITLE = "WatchAI"

# OSC 0 troca o título da janela **e** o nome do ícone de uma vez — o segundo é
# o que aparece na barra de tarefas de quem separa os dois.
_SET = "\033]0;{}\007"
_PUSH = "\033[22;0t"  # empilha o título de antes
_POP = "\033[23;0t"  # devolve o que estava lá


def _limpo(texto: str) -> str:
    """Título pronto para ir à tty: sem controles (o `\\007` fecharia o OSC no
    meio) e curto."""
    return "".join(c for c in texto if c.isprintable())[:300]


def _escrever(sequencia: str, stream: TextIO | None = None) -> bool:
    """Escreve na saída **real** do processo. `False` quando não há terminal.

    `sys.__stdout__` e não `sys.stdout` porque o alvo é a tty, não para onde o
    programa esteja escrevendo: com a saída redirecionada para um arquivo o
    título não existe, e a sequência viraria lixo no meio do texto.
    """
    saida = sys.__stdout__ if stream is None else stream
    if saida is None:  # sem console (pythonw, serviço)
        return False
    try:
        if not saida.isatty():
            return False
        saida.write(sequencia)
        saida.flush()
    except (OSError, ValueError):  # tty sumiu, ou stream já fechado
        return False
    return True


def apply(name: str = TITLE, stream: TextIO | None = None) -> bool:
    """Guarda o título atual e põe `name` na janela. Diz se chegou a escrever."""
    return _escrever(_PUSH + _SET.format(_limpo(name)), stream)


def restore(stream: TextIO | None = None) -> bool:
    """Devolve à janela o título que ela tinha antes do `apply`."""
    return _escrever(_POP, stream)


@contextmanager
def window(name: str = TITLE, stream: TextIO | None = None) -> Iterator[bool]:
    """Enquanto o bloco roda, a janela se chama `name`.

    Só desfaz o que conseguiu fazer: sem terminal, entra e sai sem escrever
    nada. E desfaz **sempre** que fez — inclusive quando o app morre por
    exceção, que é justamente quando o terminal sobrevive ao processo e ficaria
    com o nome errado na cara.
    """
    trocado = apply(name, stream)
    try:
        yield trocado
    finally:
        if trocado:
            restore(stream)
