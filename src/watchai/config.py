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
EVENTS_FILE = "events.json"
MAX_EVENTOS_SALVOS = 200
THEME_KEY = "theme"
ALERTS_KEY = "alerts"
NOTIFY_KEY = "notify"
AGENTS_KEY = "agents"


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


def events_path() -> Path:
    return config_dir() / EVENTS_FILE


def load_events() -> list[dict]:
    """O histórico da execução anterior. Lista vazia se não houver nada legível."""
    try:
        dados = json.loads(events_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(dados, list):
        return []
    return [e for e in dados if isinstance(e, dict)][:MAX_EVENTOS_SALVOS]


def save_events(eventos: list[dict]) -> bool:
    """Guarda o histórico para a próxima execução. Falhar aqui não é problema:
    perder histórico não pode derrubar nada."""
    try:
        caminho = events_path()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(
            json.dumps(eventos[:MAX_EVENTOS_SALVOS], ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        return False
    return True


def load_alerts(default: bool = True) -> bool:
    """Se os avisos (bip + notificação) estão ligados. Ligados, se não houver
    nada salvo — quem instala um monitor quer ser avisado."""
    value = load().get(ALERTS_KEY)
    return value if isinstance(value, bool) else default


def save_alerts(ligado: bool) -> bool:
    return save(**{ALERTS_KEY: bool(ligado)})


def load_agents() -> dict[str, list[str]]:
    """Agentes que **você** acrescenta, além dos que o WatchAI já conhece:

        {"agents": {"meu-agente": ["meuprog", "outro-nome"]}}

    O ecossistema ganha CLI nova toda semana; ninguém deveria esperar uma
    release para ver a própria sessão na tela. Entrada malformada é ignorada
    em silêncio — config quebrada não pode impedir o app de abrir.
    """
    bruto = load().get(AGENTS_KEY)
    if not isinstance(bruto, dict):
        return {}
    saida: dict[str, list[str]] = {}
    for chave, programas in bruto.items():
        if not isinstance(chave, str):
            continue
        if isinstance(programas, str):
            programas = [programas]
        if not isinstance(programas, list):
            continue
        nomes = [p for p in programas if isinstance(p, str) and p.strip()]
        if nomes:
            saida[chave] = nomes
    return saida


def load_notify(default: bool = False) -> bool:
    """Se a notificação do sistema está ligada — interruptor próprio, separado
    do bip.

    **Começa desligada**, ao contrário do bip: pop-up é intrusivo e quem decide
    se quer é você (`N`). O bip avisa sem atravessar a sua tela.
    """
    value = load().get(NOTIFY_KEY)
    return value if isinstance(value, bool) else default


def save_notify(ligado: bool) -> bool:
    return save(**{NOTIFY_KEY: bool(ligado)})


__all__ = [
    "config_dir",
    "config_path",
    "events_path",
    "load",
    "load_events",
    "save_events",
    "load_agents",
    "load_alerts",
    "load_notify",
    "load_theme",
    "save",
    "save_alerts",
    "save_notify",
    "save_theme",
]
