import asyncio, sys, json
from pathlib import Path
import flet as ft


UI_DIR = Path(__file__).resolve().parent
PROJECT_DIR = UI_DIR.parent
ASSETS_DIR = PROJECT_DIR / "Assets"
BACKEND_DIR = PROJECT_DIR / "Backend"

for d in (UI_DIR, BACKEND_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from components import LoadingScreen, HomeScreen, SetupWizard
from storage import save_user, get_data_dir
from poller import Poller

SETUP_FILE = get_data_dir() / "user_setup.json"


def load_setup():
    for f in [SETUP_FILE, PROJECT_DIR / "user_setup.json"]:
        try:
            if f.exists():
                saved = json.loads(f.read_text())
                if isinstance(saved, dict) and saved.get("setup_done"):
                    return saved
        except Exception:
            pass
    return None


def mark_setup_done(data: dict):
    try:
        SETUP_FILE.write_text(json.dumps({**data, "setup_done": True}))
    except Exception:
        pass


def mark_setup_pending():
    saved = load_setup() or {}
    try:
        SETUP_FILE.write_text(json.dumps({**saved, "setup_done": False}))
    except Exception:
        pass


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

    poller_ref = {"p": None}

    def stop_poller():
        if poller_ref["p"]:
            poller_ref["p"].stop()
            poller_ref["p"] = None

    def redo_setup():
        stop_poller()
        mark_setup_pending()
        page.run_task(show_setup)

    def open_home(data: dict):
        stop_poller()
        home = HomeScreen(
            plugins=data.get("plugins", []),
            name=data.get("name", ""),
            on_settings=redo_setup,
        )
        root.content = home
        page.update()

        poller = Poller(plugins=data.get("plugins", []), on_update=home.on_poll)
        home.on_refresh = poller.poll_now
        poller.start()
        poller_ref["p"] = poller

    def finish_setup(data: dict):
        save_user(data)
        mark_setup_done(data)
        open_home(data)

    async def show_setup():
        root.content = LoadingScreen()
        page.update()
        await asyncio.sleep(1.5)
        root.content = SetupWizard(on_finish=finish_setup)
        page.update()

    saved = load_setup()
    if saved:
        await asyncio.sleep(0.5)
        open_home(saved)
    else:
        await show_setup()

if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=str(ASSETS_DIR))
    else:
        ft.app(target=main, assets_dir=str(ASSETS_DIR))