import asyncio
import os
import sys
import time
import subprocess
import threading
import traceback
from pathlib import Path
import flet as ft

UI_DIR = Path(__file__).resolve().parent
PROJECT_DIR = UI_DIR.parent
ASSETS_DIR = PROJECT_DIR / "Assets"
BACKEND_DIR = PROJECT_DIR / "Backend"

for d in (UI_DIR, BACKEND_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

import control
from components import LoadingScreen, HomeScreen, SetupWizard
from storage import save_user, get_data_dir, read_json, write_json
from poller import Poller

SETUP_FILE = get_data_dir() / "user_setup.json"


def load_setup():
    for f in [SETUP_FILE, PROJECT_DIR / "user_setup.json"]:
        saved = read_json(f, None)
        if isinstance(saved, dict) and saved.get("setup_done"):
            return saved
    return None


def _write_setup(data: dict):
    try:
        write_json(SETUP_FILE, data)
    except Exception:
        pass


def mark_setup_done(data: dict):
    _write_setup({**data, "setup_done": True})


def mark_setup_pending():
    saved = load_setup() or {}
    _write_setup({**saved, "setup_done": False})


def save_plugins(plugins: list):
    saved = load_setup() or {}
    saved["plugins"] = plugins
    _write_setup({**saved, "setup_done": True})
    save_user({"plugins": plugins})

def _log(text):
    try:
        with open(get_data_dir() / "ui.log", "a") as f:
            f.write(text + "\n")
    except Exception:
        pass
_tray_proc = None


def start_tray():
    global _tray_proc
    if sys.platform != "darwin":
        return
    if _tray_proc and _tray_proc.poll() is None:
        return
    cmd = [sys.executable]
    if not getattr(sys, "frozen", False):
        cmd.append(str(PROJECT_DIR / "main.py"))
    cmd += ["--tray", str(os.getpid())]
    env = {**os.environ, "FLET_APP_STORAGE_DATA": str(get_data_dir())}
    try:
        log = open(get_data_dir() / "tray.log", "ab")
        _tray_proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                                      stdout=log, stderr=log)
    except Exception:
        traceback.print_exc()


def stop_tray():
    global _tray_proc
    if _tray_proc and _tray_proc.poll() is None:
        try:
            _tray_proc.terminate()
        except Exception:
            pass
    _tray_proc = None


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

    state = {"visible": True, "catchup": True,"shown_at":0.0}
    page.window.prevent_close = True
    loop = asyncio.get_running_loop()

    async def hide_window():
        if not state["visible"]:
            return
        if time.time() - state["shown_at"] < 1.0:
            _log("hide ignored(just shown)")
            return
        _log("hide window called")
        try:
            state["visible"]=False
            page.window.visible=False
            page.update()
        except Exception: _log("hide_window failed:\n" +traceback.format_exc())


    async def show_window():
        _log("show_window called")
        try:
            state["shown_at"]=time.time()
            state["visible"]=True
            page.window.visible=True
            page.window.minimized=False
            page.update()
            await asyncio.sleep(0.2)
            try:
                from AppKit import NSApplication
                NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            except Exception: _log("activate failed:\n" + traceback.format_exc())
            try:
                await page.window.to_front()
            except Exception:
                _log("to_front failed:\n" + traceback.format_exc())
            control.clear_missed()
            _log("show_window done")
        except Exception:
            _log("show_window failed:\n" + traceback.format_exc())

                

    async def quit_app():
        threading.Timer(2.5, lambda: os._exit(0)).start()
        stop_poller()
        server.close()
        stop_tray()
        try:
            await page.window.destroy()
        except Exception:
            pass

    def on_window_event(e):
        _log(f"window event: type={getattr(e, 'type', None)} data={getattr(e, 'data', None)}")
        if getattr(e, "type", None) == ft.WindowEventType.CLOSE:
            page.run_task(hide_window)

    page.window.on_event = on_window_event

    def threadsafe(coro_fn):
        def runner():
            _log(f"command received: {coro_fn.__name__}")
            asyncio.run_coroutine_threadsafe(coro_fn(), loop)
        return runner

    def do_recheck():
        p = poller_ref["p"]
        if p:
            p.poll_now()

    server = control.Server({
        "open": threadsafe(show_window),
        "recheck": do_recheck,
        "quit": threadsafe(quit_app),
        "ping": lambda: None,
    })
    start_tray()

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

        def on_poll(added, failed, fresh):
            if fresh and (not state["visible"] or state["catchup"]):
                control.add_missed(len(fresh))
            if not failed:
                state["catchup"] = False
            home.on_poll(added, failed)

        def start_poller(plugins):
            stop_poller()
            poller = Poller(plugins=plugins, on_update=on_poll)
            home.on_refresh = poller.poll_now
            poller.start()
            poller_ref["p"] = poller

        def plugins_changed(plugins):
            save_plugins(plugins)
            start_poller(plugins)

        home.on_plugins_changed = plugins_changed
        root.content = home
        page.update()
        start_poller(data.get("plugins", []))

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

