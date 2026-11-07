import os
import subprocess
import sys
from pathlib import Path
import control
import sound

WINDOWS = sys.platform.startswith("win")


def _esc(text):
    t = str(text).replace("\\", "\\\\").replace('"', '\\"')
    return t.replace("\n", " ").replace("\r", " ").replace("\t", " ")


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
    if control.send("notify", {"title": str(title), "body": str(body), "url": url or ""}, target="tray"):
        return
    script = f'''
    try
        tell application "Notifio" to display notification "{_esc(body)}" with title "{_esc(title)}"
    on error
        tell application "System Events" to display notification "{_esc(body)}" with title "{_esc(title)}"
    end try
    '''
    subprocess.run(["osascript", "-e", script], check=False, timeout=5)


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
            _mac(title, body, url)
        elif WINDOWS:
            _windows(title, body, url)
    except Exception:
        pass