"""Helpers de formatação de texto/tempo (puros, sem Textual)."""

from __future__ import annotations

from datetime import datetime, timedelta

ELLIPSIS = "…"
DASH = "—"


def ellipsize(text: str, width: int) -> str:
    """Trunca `text` para caber em `width` colunas: 'telegram-downloa…'."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return ELLIPSIS
    return text[: width - 1].rstrip() + ELLIPSIS


def fmt_clock(dt: datetime) -> str:
    """17:42:08"""
    return dt.strftime("%H:%M:%S")


def _secs(delta: timedelta) -> int:
    return max(0, int(delta.total_seconds()))


def fmt_hms(delta: timedelta) -> str:
    """Tempo total de sessão: 00:04:32"""
    s = _secs(delta)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def fmt_timer(delta: timedelta) -> str:
    """Tempo no estado atual, compacto e alinhável: 01:42 / 1:05:12"""
    s = _secs(delta)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


def fmt_span(seconds: float) -> str:
    """Duração larga, curta de ler: 45s · 7m · 1h20m · 4d12h.

    Para distância no tempo (quando a janela de limite zera, que idade tem o
    número), não para contador que anda na tela: aqui não há dois-pontos nem
    zeros à esquerda, e só as duas unidades que importam aparecem.
    """
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        horas, minutos = s // 3600, (s % 3600) // 60
        return f"{horas}h{minutos:02d}m" if minutos else f"{horas}h"
    dias, horas = s // 86400, (s % 86400) // 3600
    return f"{dias}d{horas:02d}h" if horas else f"{dias}d"
