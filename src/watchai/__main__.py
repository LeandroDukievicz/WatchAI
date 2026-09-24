"""Linha de comando: `watchai` · `python -m watchai` · `python main.py`."""

from __future__ import annotations

import argparse

from . import __version__, termtitle
from .app import WatchAIApp


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="watchai",
        description="Monitor de sessões de IA no terminal (Claude Code, Codex, Gemini…).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="roda com dados simulados, sem olhar os processos da máquina",
    )
    parser.add_argument(
        "--theme",
        metavar="TEMA",
        help="tema desta execução (watchai, light, dark, night-owl, vampire, "
        "cyberpunk, steampunk, grey); não altera o salvo",
    )
    parser.add_argument("--version", action="version", version=f"watchai {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse(argv)
    # A janela passa a se chamar WatchAI enquanto o app está no ar, e volta ao
    # nome de antes na saída. Fica aqui, e não dentro do app, para não disputar
    # a saída com o Textual: a troca acontece antes de ele assumir a tela e
    # depois de ele devolvê-la.
    with termtitle.window():
        WatchAIApp(mock=args.mock, theme_key=args.theme).run()


if __name__ == "__main__":
    main()
