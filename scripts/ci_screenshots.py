#!/usr/bin/env python3
"""Exporta todas as telas em SVG para inspeção visual nos artifacts do CI."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from watchai.app import WatchAIApp


async def export(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    app = WatchAIApp(seed=3, mock=True, theme_key="watchai")
    async with app.run_test(size=(150, 40)) as pilot:
        await pilot.pause()
        (destination / "dashboard.svg").write_text(app.export_screenshot(), encoding="utf-8")
        await pilot.press("enter")
        await pilot.pause()
        (destination / "details.svg").write_text(app.export_screenshot(), encoding="utf-8")
        await pilot.press("escape", "question_mark")
        await pilot.pause()
        (destination / "help.svg").write_text(app.export_screenshot(), encoding="utf-8")
        await pilot.press("escape", "t")
        await pilot.pause()
        (destination / "themes.svg").write_text(app.export_screenshot(), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    asyncio.run(export(args.destination))


if __name__ == "__main__":
    main()
