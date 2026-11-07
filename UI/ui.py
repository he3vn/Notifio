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
from components import LoadingScreen, LandingScreen, HomeScreen
from storage import save_user, get_data_dir, read_json, write_json
from poller import Poller

WINDOWS = sys.platform.startswith("win")
MAC = sys.platform == "darwin"
SETUP_FILE = get_data_dir() / "user_setup.json"


def load_setup():
    saved = read_json(SETUP_FILE, None)
    if saved is None:
        saved = read_json(PROJECT_DIR / "user_setup.json", None)
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


import atexit
atexit.register(lambda: _log("python exiting"))

_tray_proc = None


def _flet_client_pid():
    """PID of the Flet desktop client window process for this app.

    The client is launched by flet_desktop with our assets dir as its last
    argument, so that string uniquely identifies our window process (there
    can be other Flet apps running on the machine).
    """
    if not MAC:
        return None
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid=,command="], capture_output=True, text=True, timeout=3
        ).stdout
    except Exception:
        return None
    marker = str(ASSETS_DIR)
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_text, _, cmd = line.partition(" ")
        if "Flet.app/Contents/MacOS/Flet" in cmd and marker in cmd:
            try:
                return int(pid_text)
            except ValueError:
                continue
    return None


def _mac_client_app():
    if not MAC:
        return None
    pid = _flet_client_pid()
    if not pid:
        return None
    try:
        from AppKit import NSRunningApplication
        return NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    except Exception:
        return None


def _activate_client():
    """Bring the Flet window process to the front (the Python process has no UI)."""
    if not MAC:
        return
    try:
        app = _mac_client_app()
        if app is not None:
            app.activateWithOptions_(1)  # NSApplicationActivateIgnoringOtherApps
    except Exception:
        _log("activate client failed:\n" + traceback.format_exc())


def start_tray():
    global _tray_proc
    if not (MAC or WINDOWS):
        return
    if _tray_proc and _tray_proc.poll() is None:
        return
    # Dev mode (not frozen): don't run the tray under raw python. macOS ties
    # notification permission to the bundle id, and python's bundle
    # (org.python.python) is permanently denied with no reset path on modern
    # macOS — notifications from it never appear (silently, or via Script
    # Editor). Instead, spawn the built Notifio binary as the tray helper so
    # notifications are attributed to the real app and can be allowed once.
    cmd = None
    if not getattr(sys, "frozen", False) and MAC:
        built = PROJECT_DIR / "dist" / "Notifio.app" / "Contents" / "MacOS" / "Notifio"
        if built.is_file():
            cmd = [str(built)]
    if cmd is None:
        cmd = [sys.executable]
        if not getattr(sys, "frozen", False):
            cmd.append(str(PROJECT_DIR / "main.py"))
    cmd += ["--tray", str(os.getpid())]
    env = {**os.environ, "FLET_APP_STORAGE_DATA": str(get_data_dir())}
    options = {}
    if WINDOWS:
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        log = open(get_data_dir() / "tray.log", "ab")
        _tray_proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                                      stdout=log, stderr=log, **options)
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
        page.window.title_bar_hidden = MAC
        if MAC:
            # Menu-bar app: no Dock tile. Must be set before the window is
            # first shown — runtime changes to this property are ignored by
            # the Flet client. This is what makes closing the window leave
            # no icon in the Dock while the tray keeps the app alive.
            page.window.skip_task_bar = True

    root = ft.Container(expand=True)
    page.add(root)

    poller_ref = {"p": None}
    home_ref = {"h": None}

    def stop_poller():
        if poller_ref["p"]:
            poller_ref["p"].stop()
            poller_ref["p"] = None

    async def pause_media():
        h = home_ref["h"]
        if h:
            try:
                await h.pause_media()
            except Exception:
                _log("pause_media failed:\n" + traceback.format_exc())

    async def play_media():
        h = home_ref["h"]
        if h:
            try:
                await h.play_media()
            except Exception:
                _log("play_media failed:\n" + traceback.format_exc())

    def drop_media():
        h = home_ref["h"]
        if h:
            try:
                h.drop_media()
            except Exception:
                _log("drop_media failed:\n" + traceback.format_exc())

    state = {"visible": True, "catchup": True, "shown_at": 0.0}
    page.window.prevent_close = True
    loop = asyncio.get_running_loop()

    def set_taskbar_hidden(hidden):
        if not WINDOWS:
            return
        try:
            page.window.skip_task_bar = hidden
        except Exception:
            _log("skip_task_bar failed:\n" + traceback.format_exc())

    async def hide_window():
        if not state["visible"]:
            return
        if time.time() - state["shown_at"] < 1.0:
            _log("hide ignored(just shown)")
            return
        _log("hide window called")
        try:
            state["visible"] = False
            # Pause playback while hidden — never tear the player down here,
            # that teardown racing the window-hide is what crashes mpv.
            await pause_media()
            set_taskbar_hidden(True)
            # Never use `visible = False` here: in flet 1.1.0 hiding the last
            # window makes the desktop client quit, which kills the poller and
            # tears down mpv mid-playback (SIGSEGV in the Mpv core thread).
            # Minimizing keeps the client, tray and background polling alive
            # while taking the window off screen.
            page.window.minimized = True
            page.update()
        except Exception:
            _log("hide_window failed:\n" + traceback.format_exc())

    async def show_window():
        _log("show_window called")
        try:
            state["shown_at"] = time.time()
            state["visible"] = True
            set_taskbar_hidden(False)
            page.window.minimized = False
            page.update()
            await asyncio.sleep(0.2)
            _activate_client()
            try:
                await page.window.to_front()
            except Exception:
                _log("to_front failed:\n" + traceback.format_exc())
            await play_media()
            control.clear_missed()
            _log("show_window done")
        except Exception:
            _log("show_window failed:\n" + traceback.format_exc())

    async def quit_app():
        threading.Timer(5.0, lambda: os._exit(0)).start()
        stop_poller()
        # Media teardown must be slow and serialized, or mpv segfaults the
        # client: pause first, let it settle, THEN drop the widget, let that
        # settle, and only then tear down the window/platform.
        await pause_media()
        await asyncio.sleep(1.0)
        drop_media()
        await asyncio.sleep(2.0)
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

    def on_disconnect(e):
        _log("page disconnected")

    try:
        page.on_disconnect = on_disconnect
    except Exception:
        _log("on_disconnect not supported")

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
        "hide": threadsafe(hide_window),
        "recheck": do_recheck,
        "quit": threadsafe(quit_app),
        "ping": lambda: None,
    })
    start_tray()

    def open_home(data: dict):
        stop_poller()
        home = HomeScreen(
            plugins=data.get("plugins", []),
            name=data.get("name", ""),
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
        home.on_settings = redo_setup
        home_ref["h"] = home
        root.content = home
        page.update()
        start_poller(data.get("plugins", []))

    def redo_setup():
        stop_poller()
        home_ref["h"] = None
        root.content = LandingScreen(page=page, on_finish=finish_setup)
        page.update()

    def finish_setup(plugins):
        data = {**(load_setup() or {}), "plugins": plugins}
        mark_setup_done(data)
        save_user({"plugins": plugins})
        open_home(data)

    saved = load_setup()
    if saved:
        open_home(saved)
    else:
        root.content = LandingScreen(page=page, on_finish=finish_setup)
        page.update()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=str(ASSETS_DIR))
    else:
        ft.app(target=main, assets_dir=str(ASSETS_DIR))