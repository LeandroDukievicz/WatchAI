#!/usr/bin/env python3
"""Captura a TUI do WatchAI como PNG — pelo caminho que funciona.

Três armadilhas aqui já custaram tempo a quem tentou refazer as capturas, e é
por elas que este script existe em vez de uma linha de comando avulsa:

* **as cores.** O Rich decide se emite cor ao criar o console. Com `NO_COLOR`
  no ambiente, ou sem `COLORTERM`, o SVG sai em escala de cinza — e aí os oito
  temas ficam idênticos, o que é fácil de não perceber até a galeria estar
  publicada. O ambiente é ajustado aqui, antes de importar o app.
* **o renderizador.** O SVG do Textual usa fontes e `<tspan>` de um jeito que o
  ImageMagick erra (troca a fonte, desalinha tudo) e que o Inkscape empacotado
  como snap nem abre. Quem acerta é o Chrome headless: é o mesmo motor que
  mostra o SVG no navegador.
* **o tamanho.** A janela do Chrome é maior que o alvo de propósito: o
  `-resize` para baixo é o que deixa o texto nítido.

Uso:

    scripts/screenshot.py docs/screenshot.png              # sessões reais
    scripts/screenshot.py --mock docs/demo.png            # dados simulados
    scripts/screenshot.py --mock --theme vampire fora.png
    scripts/screenshot.py --mock --temas docs/theme-shots  # um PNG por tema
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Antes de qualquer import do app: é na criação do console que o Rich decide.
os.environ.pop("NO_COLOR", None)
os.environ.setdefault("COLORTERM", "truecolor")
os.environ.setdefault("TERM", "xterm-256color")

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

# A janela do Chrome, e a largura final depois do resize.
JANELA = (1848, 929)
LARGURA_FINAL = 1400
CORES = 128  # paleta reduzida: corta o peso do PNG sem marcar o texto


def navegador() -> str:
    for nome in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    raise SystemExit(
        "preciso do Chrome ou do Chromium: é o único renderizador que acerta o "
        "SVG do Textual (o ImageMagick erra as fontes, o Inkscape do snap não abre)"
    )


def conversor() -> list[str]:
    if shutil.which("magick"):
        return ["magick"]
    if shutil.which("convert"):
        return ["convert"]
    raise SystemExit("preciso do ImageMagick (`magick` ou `convert`) para redimensionar")


async def _svg(tema: str, mock: bool, seed: int, tamanho: tuple[int, int]) -> str:
    from watchai.app import WatchAIApp
    from watchai.notify import Notifier

    app = WatchAIApp(seed=seed, mock=mock, theme_key=tema, notifier=Notifier(None))
    async with app.run_test(size=tamanho) as pilot:
        await pilot.pause()
        if not mock:
            # Duas varreduras: o estado de um agente sai da diferença de CPU
            # entre duas leituras, e a primeira não tem com o que comparar.
            for _ in range(2):
                app.scan()
                await app.workers.wait_for_complete()
                await pilot.pause()
        return app.export_screenshot()


def capturar(destino: Path, *, tema: str, mock: bool, seed: int, tamanho: tuple[int, int]) -> None:
    svg = asyncio.run(_svg(tema, mock, seed, tamanho))
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        # O Chrome só abre arquivo com extensão .svg, e por file:// absoluto.
        origem = Path(tmp) / "tela.svg"
        origem.write_text(svg, encoding="utf-8")
        bruto = Path(tmp) / "bruto.png"
        subprocess.run(
            [navegador(), "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
             f"--screenshot={bruto}", f"--window-size={JANELA[0]},{JANELA[1]}",
             origem.as_uri()],
            check=True, capture_output=True,
        )
        if not bruto.exists():
            raise SystemExit("o navegador não gerou o PNG — rode sem --headless para ver o erro")
        subprocess.run(
            [*conversor(), str(bruto), "-resize", f"{LARGURA_FINAL}x",
             "-colors", str(CORES), "-strip", str(destino)],
            check=True, capture_output=True,
        )
    print(f"{destino}  ({destino.stat().st_size // 1024} KB)")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("destino", type=Path, help="PNG de saída (ou a pasta, com --temas)")
    p.add_argument("--mock", action="store_true", help="dados simulados em vez das sessões da máquina")
    p.add_argument("--theme", default="watchai", help="tema da captura (padrão: watchai)")
    p.add_argument("--temas", action="store_true", help="um PNG por tema, dentro da pasta indicada")
    p.add_argument("--seed", type=int, default=3, help="semente do mock, para a cena ser sempre a mesma")
    p.add_argument("--size", default="150x36", help="tamanho do terminal, em colunas x linhas")
    args = p.parse_args(argv)

    largura, _, altura = args.size.partition("x")
    tamanho = (int(largura), int(altura))

    if not args.temas:
        capturar(args.destino, tema=args.theme, mock=args.mock, seed=args.seed, tamanho=tamanho)
        return

    from watchai.theme import PALETTES

    for palette in PALETTES:
        capturar(
            args.destino / f"{palette.key}.png",
            tema=palette.key, mock=args.mock, seed=args.seed, tamanho=tamanho,
        )


if __name__ == "__main__":
    main()
