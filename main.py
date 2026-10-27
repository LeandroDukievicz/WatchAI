#!/usr/bin/env python3
"""Ponto de entrada: `python main.py`.

Com o pacote instalado (`pip install -e .`) o import funciona direto. Sem
instalar nada, o `src/` entra no path para que um clone recém-baixado rode na
hora — é o que o README promete.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from watchai.__main__ import main  # noqa: E402  (precisa do path acima)

if __name__ == "__main__":
    # Com o código de saída, como o `python -m watchai` já fazia. Sem ele, um
    # `--install-statusline` que falhou saía com 0 e qualquer script que
    # encadeasse o comando seguia adiante achando que tinha dado certo.
    raise SystemExit(main())
