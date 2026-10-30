import os
from pathlib import Path
import rumps
import control


def _icon():
    root = Path(os.environ.get("NOTIFIO_ROOT", Path(__file__).resolve().parents[1]))
    for name in ("tray.png", "icon.png"):
        p = root / "Assets" / name
        if p.is_file():
            return str(p)
    return None


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Tray(rumps.App):
    def __init__(self, parent_pid):
        super().__init__("Notifio", icon=_icon(), template=False, quit_button=None)
        self.parent_pid = parent_pid
        self._last = -1
        self._misses = 0
        self.missed = rumps.MenuItem("No missed notifications", callback=self._open)
        self.menu = [
            rumps.MenuItem("Open Notifio", callback=self._open),
            self.missed,
            rumps.MenuItem("Recheck now", callback=self._recheck),
            None,
            rumps.MenuItem("Quit Notifio", callback=self._quit),
        ]

    def _tick(self, _):
        # Parent process is gone: nothing left to control, so the tray exits too.
        if not _alive(self.parent_pid):
            rumps.quit_application()
            return

        # Parent exists but the socket server isn't answering: exit after 5 misses (~10s).
        if control.send("ping"):
            self._misses = 0
        else:
            self._misses += 1
            if self._misses >= 5:
                rumps.quit_application()
                return

        n = control.get_missed()
        if n != self._last:
            self._last = n
            self.missed.title = ("No missed notifications" if n == 0
                                 else f"{n} missed notification{'s' if n != 1 else ''}")

    def _open(self, _):
        if not control.send("open"):
            rumps.notification("Notifio", "", "Couldn't reach the app. Try relaunching it.")

    def _recheck(self, _):
        control.send("recheck")

    def _quit(self, _):
        control.send("quit")
        rumps.quit_application()


def run(parent_pid):
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass
    app = Tray(parent_pid)
    rumps.Timer(app._tick, 2).start()
    app.run()