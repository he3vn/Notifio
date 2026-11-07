import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
import control
import sound

WINDOWS = sys.platform.startswith("win")
APP_ID = "Notifio"
_aumid_done = False

TN_PATHS = (
    "/opt/homebrew/bin/terminal-notifier",
    "/usr/local/bin/terminal-notifier",
)


def _plain(text):
    t = str(text or "").replace("&", "and").replace("<", "").replace(">", "")
    return t.replace("\n", " ").replace("\r", " ").strip()


def _root():
    return Path(os.environ.get("NOTIFIO_ROOT", Path(__file__).resolve().parents[1]))


def _icon():
    for name in ("icon.png", "tray.png"):
        p = _root() / "Assets" / name
        if p.is_file():
            return str(p)
    return None


# --------------------------------------------------------------------------
# macOS
# --------------------------------------------------------------------------
def _find_tn():
    """terminal-notifier: bundled copy first, then Homebrew / PATH."""
    bundled = _root() / "Assets" / "terminal-notifier"
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    return shutil.which("terminal-notifier") or next(
        (p for p in TN_PATHS if os.path.exists(p)), None)


def _open_app_command():
    """Shell command that brings Notifio to the front (a second launch just
    sends 'open' to the running instance and exits)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{_root() / "main.py"}"'


def _native_mac(title, body, url):
    """Native notification (shows in Notification Center). Returns True if posted."""
    tn = _find_tn()
    if not tn:
        return False
    cmd = [tn, "-title", str(title or "Notifio"), "-message", str(body or " "),
           "-group", "notifio"]
    # NOTE: no -group reuse across items would replace the previous banner, so
    # give every notification its own group id.
    cmd[-1] = f"notifio-{time.time_ns()}"
    if url:
        cmd += ["-open", url]
    else:
        cmd += ["-execute", _open_app_command()]
    icon = _icon()
    if icon:
        cmd += ["-appIcon", icon]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception:
        traceback.print_exc()
        return False
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or "turned off" in out.lower():
        print(f"notifier: terminal-notifier failed: {out.strip()}", file=sys.stderr)
        return False
    return True


def _to_tray(title, body, url):
    """Fallback: tray process draws a clickable banner (macOS) or balloon (Windows)."""
    args = {"title": str(title or "Notifio"), "body": str(body or ""), "url": url or ""}
    for _ in range(6):
        if control.send("notify", args, target="tray"):
            return True
        time.sleep(0.5)
    return False


def _mac(title, body, url):
    if _native_mac(title, body, url):
        return
    if not _to_tray(title, body, url):
        print("notifier: no way to show the notification", file=sys.stderr)


# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------
def _register_aumid():
    global _aumid_done
    if _aumid_done:
        return
    _aumid_done = True
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              rf"Software\Classes\AppUserModelId\{APP_ID}") as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_ID)
            icon = _icon()
            if icon:
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, icon)
    except Exception:
        traceback.print_exc()


def _windows(title, body, url):
    try:
        _register_aumid()
        from winotify import Notification, audio
        options = {
            "app_id": APP_ID,
            "title": _plain(title) or "Notifio",
            "msg": _plain(body) or " ",
            "duration": "short",
        }
        icon = _icon()
        if icon:
            options["icon"] = icon
        toast = None
        if url:
            try:
                toast = Notification(**options, launch=url)
            except TypeError:
                toast = None
        if toast is None:
            toast = Notification(**options)
        toast.set_audio(audio.Silent, loop=False)
        toast.show()
    except Exception:
        traceback.print_exc()
        _to_tray(title, body, url)


# --------------------------------------------------------------------------
def _deliver(title, body, url):
    try:
        if sys.platform == "darwin":
            _mac(title, body, url)
        elif WINDOWS:
            _windows(title, body, url)
    except Exception:
        traceback.print_exc()


def send(title, body="", url=None):
    """Send a notification. Never raises, never blocks the caller."""
    try:
        sound.alert()
    except Exception:
        traceback.print_exc()
    threading.Thread(target=_deliver, args=(title, body, url), daemon=True).start()