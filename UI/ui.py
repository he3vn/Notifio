import asyncio
import sys
from pathlib import Path
import flet as ft

# Ensure UI directory is in sys.path for components import
UI_DIR = Path(__file__).resolve().parent
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

from components import LoadingScreen, HomeScreen


def main(page: ft.Page):
    page.title = "Notifio"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#FFF9E6"
    page.padding = 0
    page.spacing = 0

    if hasattr(page, "window") and page.window:
        page.window.width = 1280
        page.window.height = 800
        page.window.min_width = 500
        page.window.min_height = 520
        page.window.title_bar_hidden = True

    root = ft.Container(content=LoadingScreen(), expand=True)
    page.add(root)

    async def boot():
        await asyncio.sleep(2.0)
        root.content = HomeScreen(on_enter=lambda: None)
        page.update()

    page.run_task(boot)


if __name__ == "__main__":
    ft.run(main) if hasattr(ft, "run") else ft.app(target=main)