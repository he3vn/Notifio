import asyncio, sys
from pathlib import Path
import flet as ft

UI_DIR = Path(__file__).resolve().parent
PROJECT_DIR = UI_DIR.parent
ASSETS_DIR = PROJECT_DIR / "Assets"

if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

from components import LoadingScreen, HomeScreen, SetupWizard
from storage import save_user


async def main(page: ft.Page):
    page.title = "Notifio"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#08090a"
    page.padding, page.spacing = 0, 0

    page.fonts = {
        "Inter": "fonts/Inter-Regular.ttf",
        "Inter-Medium": "fonts/Inter-Medium.ttf",
        "Inter-SemiBold": "fonts/Inter-SemiBold.ttf",
        "Inter-Bold": "fonts/Inter-Bold.ttf",
        "Inter-Light": "fonts/Inter-Light.ttf",
    }
    page.theme = ft.Theme(font_family="Inter")

    if hasattr(page, "window") and page.window:
        page.window.width, page.window.height = 1280, 800
        page.window.min_width, page.window.min_height = 500, 520
        page.window.title_bar_hidden = True

    root = ft.Container(content=LoadingScreen(), expand=True)
    page.add(root)

    def finish_setup(data: dict):
        save_user(data)
        root.content = HomeScreen(name=data.get("name", ""))
        page.update()

    await asyncio.sleep(2.5)
    root.content = SetupWizard(on_finish=finish_setup)
    page.update()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=str(ASSETS_DIR))
    else:
        ft.app(target=main, assets_dir=str(ASSETS_DIR))
