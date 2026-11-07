import os
import queue
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
import control

WINDOWS = sys.platform.startswith("win")


def _icon(names):
    root = Path(os.environ.get("NOTIFIO_ROOT", Path(__file__).resolve().parents[1]))
    for name in names:
        p = root / "Assets" / name
        if p.is_file():
            return str(p)
    return None


def _alive(pid):
    if WINDOWS:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return bool(ok) and code.value == 259
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _missed_text(n):
    return "No missed notifications" if n == 0 else f"{n} missed notification{'s' if n != 1 else ''}"


def _open_target(url):
    if url:
        try:
            webbrowser.open(url)
            return
        except Exception:
            traceback.print_exc()
    control.send("open")


def _prepare_mac():
    """Menu-bar-only agent (no Dock icon) that opts out of App Nap."""
    try:
        from Foundation import NSBundle, NSProcessInfo
        info = NSBundle.mainBundle().infoDictionary()
        if info is not None:
            info["LSUIElement"] = "1"
        # NSActivityUserInitiatedAllowingIdleSystemSleep
        global _activity
        _activity = NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
            0x00FFFFFF & ~(1 << 20), "Notifio background notifications")
    except Exception:
        traceback.print_exc()
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        traceback.print_exc()


_activity = None


def _run_mac(parent_pid):
    _prepare_mac()
    import rumps
    toasts = None
    try:
        from toast import ToastManager
        toasts = ToastManager(_icon(("icon.png", "tray.png")))
    except Exception:
        traceback.print_exc()

    pending = queue.Queue()

    class Tray(rumps.App):
        def __init__(self):
            super().__init__("Notifio", icon=_icon(("tray.png", "icon.png")), template=False, quit_button=None)
            self.parent_pid = parent_pid
            self._last = -1
            self._misses = 0
            self.server = control.Server({"notify": pending.put, "ping": lambda: None}, target="tray")
            self.missed = rumps.MenuItem("No missed notifications", callback=self._open)
            self.menu = [
                rumps.MenuItem("Open Notifio", callback=self._open),
                self.missed,
                rumps.MenuItem("Recheck now", callback=self._recheck),
                None,
                rumps.MenuItem("Quit Notifio", callback=self._quit),
            ]

        def _exit(self):
            self.server.close()
            rumps.quit_application()

        def _tick(self, _):
            try:
                if not _alive(self.parent_pid):
                    self._exit()
                    return
                if control.send("ping"):
                    self._misses = 0
                else:
                    self._misses += 1
                    if self._misses >= 5:
                        self._exit()
                        return
                n = control.get_missed()
                if n != self._last:
                    self._last = n
                    self.missed.title = _missed_text(n)
            except Exception:
                traceback.print_exc()

        def _drain(self, _):
            if toasts:
                try:
                    toasts.tick()
                except Exception:
                    traceback.print_exc()
            while True:
                try:
                    item = pending.get_nowait()
                except queue.Empty:
                    return
                title = item.get("title") or "Notifio"
                body = item.get("body") or ""
                url = item.get("url") or ""
                try:
                    if toasts is None:
                        raise RuntimeError("toast unavailable")
                    toasts.show(title, body, lambda url=url: _open_target(url))
                except Exception:
                    traceback.print_exc()
                    try:  # last resort: native banner (only works from a signed .app)
                        rumps.notification(title=title, subtitle="", message=body, sound=False)
                    except Exception:
                        traceback.print_exc()

        def _open(self, _):
            control.send("open")

        def _recheck(self, _):
            control.send("recheck")

        def _quit(self, _):
            control.send("quit")
            self._exit()

    app = Tray()
    # keep references: rumps timers stop if they are garbage collected
    app._timers = [rumps.Timer(app._tick, 2), rumps.Timer(app._drain, 0.4)]
    for t in app._timers:
        t.start()
    app.run()


def _run_windows(parent_pid):
    import pystray
    from PIL import Image

    path = _icon(("tray.ico", "tray.png", "icon.png"))
    image = Image.open(path) if path else Image.new("RGBA", (64, 64), (94, 106, 210, 255))

    def open_app(icon, item):
        control.send("open")

    def recheck(icon, item):
        control.send("recheck")

    def quit_app(icon, item):
        control.send("quit")
        icon.stop()

    def missed_label(item):
        return _missed_text(control.get_missed())

    menu = pystray.Menu(
        pystray.MenuItem("Open Notifio", open_app, default=True),
        pystray.MenuItem(missed_label, open_app),
        pystray.MenuItem("Recheck now", recheck),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Notifio", quit_app),
    )
    icon = pystray.Icon("Notifio", image, "Notifio", menu)

    def watch():
        misses = 0
        last = -1
        while True:
            time.sleep(2)
            if not _alive(parent_pid):
                icon.stop()
                return
            if control.send("ping"):
                misses = 0
            else:
                misses += 1
                if misses >= 5:
                    icon.stop()
                    return
            n = control.get_missed()
            if n != last:
                last = n
                try:
                    icon.update_menu()
                except Exception:
                    pass

    def setup(icon):
        icon.visible = True
        threading.Thread(target=watch, daemon=True).start()

    icon.run(setup)


def run(parent_pid):
    if WINDOWS:
        _run_windows(parent_pid)
    else:
        _run_mac(parent_pid)