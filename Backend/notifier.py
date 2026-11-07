import os
import sys
import traceback
from pathlib import Path
import control
import sound

WINDOWS = sys.platform.startswith("win")


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
    """Post a macOS notification without Script Editor ever being involved.

    Preferred route: hand it to the tray helper process, which posts it with
    UNUserNotificationCenter. The toast is attributed to the Notifio bundle and
    clicking it opens the item's page (or the app window if there is no link).
    """
    args = {"title": str(title or "Notifio"), "body": str(body or ""), "url": url or ""}
    if control.send("notify", args, target="tray"):
        return
    # No osascript fallback on purpose: macOS attributes those toasts to
    # Script Editor/Terminal and clicking them opens that app instead of the
    # item page. If the tray is not up yet, drop the toast rather than show a
    # misleading one.
    print("notifier: tray helper not reachable, notification dropped", file=sys.stderr)


def _windows(title, body, url):
    from winotify import Notification, audio
    options = {
        "app_id": "Notifio",
        "title": _plain(title) or "Notifio",
        "msg": _plain(body) or " ",
        "duration": "short",
    }
    icon = _icon()
    if icon:
        options["icon"] = icon
    if url:
        try:
            toast = Notification(**options, launch=url)
        except TypeError:
            toast = Notification(**options)
    else:
        toast = Notification(**options)
    toast.set_audio(audio.Silent, loop=False)
    toast.show()


def send(title, body="", url=None):
    """Send a notification. Never raises."""
    try:
        sound.alert()
    except Exception:
        traceback.print_exc()
    try:
        if sys.platform == "darwin":
            _mac(title, body, url)
        elif WINDOWS:
            _windows(title, body, url)
    except Exception:
        traceback.print_exc()
