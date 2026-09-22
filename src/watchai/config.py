"""Preferências do usuário, guardadas entre execuções.

Um JSON pequeno em `$XDG_CONFIG_HOME/watchai/config.json` (ou
`~/.config/watchai/config.json`). Nada aqui pode derrubar a TUI: disco cheio,
arquivo corrompido ou diretório sem permissão viram silenciosamente o padrão.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_DIR = "watchai"
FILE_NAME = "config.json"
THEME_KEY = "theme"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base).expanduser() / APP_DIR


def config_path() -> Path:
    return config_dir() / FILE_NAME


def load() -> dict[str, Any]:
    """O que estiver salvo, ou `{}` se não houver nada legível."""
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(**changes: Any) -> bool:
    """Grava as mudanças por cima do que já existe. True se conseguiu."""
    data = load()
    data.update(changes)
    try:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


def load_theme() -> str | None:
    """A chave do tema salvo, se for uma string."""
    value = load().get(THEME_KEY)
    return value if isinstance(value, str) else None


def save_theme(key: str) -> bool:
    return save(**{THEME_KEY: key})


__all__ = ["config_dir", "config_path", "load", "load_theme", "save", "save_theme"]
