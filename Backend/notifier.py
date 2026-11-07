import os
import sys
import time
import traceback
from pathlib import Path
import control
import sound

WINDOWS = sys.platform.startswith("win")

# Set by the UI: a callable that (re)starts the tray process on macOS.
tray_starter = None


def _plain(text):
    t = str(text or "").replace("&", "and").replace("<", "").replace(">", "")
    return t.replace("\n", " ").replace("\r", " ").strip()


def _icon():
    root = Path(os.environ.get("NOTIFIO_ROOT", Path(__file__).resolve().parents[1]))
    for name in ("icon.png", "tray.png"):
        p = root / "Assets" / name
        if p.is_file():
            return str(p)
    return None


def _mac(title, body, url):
    """Hand the notification to the tray process, which shows a clickable
    banner (see toast.py). Clicking it opens `url` in the browser."""
    payload = {"title": str(title), "body": str(body), "url": url or ""}
    if control.send("notify", payload, target="tray"):
        return True
    # tray died or hasn't finished starting: (re)start it and retry for a few seconds
    if tray_starter:
        try:
            tray_starter()
        except Exception:
            traceback.print_exc()
    for _ in range(12):
        time.sleep(0.5)
        if control.send("notify", payload, target="tray"):
            return True
    return False


def _windows(title, body, url):
    from winotify import Notification, audio
    options = {"app_id": "Notifio", "title": _plain(title) or "Notifio", "msg": _plain(body) or " ", "duration": "short"}
    icon = _icon()
    if icon:
        options["icon"] = icon
    if url:
        try:
            toast = Notification(**options, launch=url)
        except TypeError:
            toast = Notification(**options)
            toast.add_actions(label="Open", launch=url)
    else:
        toast = Notification(**options)
    toast.set_audio(audio.Silent, loop=False)
    toast.show()


def send(title, body="", url=None):
    try:
        sound.alert()
        if sys.platform == "darwin":
            if not _mac(title, body, url):
                print("notifier: tray unreachable, notification dropped:", title, flush=True)
        elif WINDOWS:
            _windows(title, body, url)
    except Exception:
        traceback.print_exc()
