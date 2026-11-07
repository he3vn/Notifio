import subprocess
import sys
import threading
import time
from pathlib import Path
import app_settings

WINDOWS=sys.platform.startswith("win")
COOLDOWN=10.0
MAC_DEFAULT= "/System/Library/Sounds/Glass.aiff"

_lock=threading.Lock()
_last=0.0

def _sound_path():
    path=app_settings.get("sound_file")
    if path and Path(path).is_file():
        return path
    return ""

def _play_mac(path):
    target=path or MAC_DEFAULT
    subprocess.run(["afplay", target],timeout=30,
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def _play_windows(path):
    if path:
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW
        mci("close notifio_alert", None, 0, 0)
        if mci(f'open "{path}" alias notifio_alert',None,0,0):
            mci("play notifio_alert",None,0,0)
            return
    import winsound
    winsound.MessageBeep(winsound.MB_ICONASTERISK)

def _run(path):
    try:
        if sys.platform=="darwin":
            _play_mac(path)
        elif WINDOWS:
            _play_windows(path)
    except Exception:
        pass

def alert(force=False):
    global _last
    if not force and not app_settings.get("sound"):
        return
    with _lock:
        now=time.monotonic()
        if not force and now - _last < COOLDOWN:
            return
        _last=now
    threading.Thread(target=_run, args=(_sound_path(),), daemon=True).start()
    
    
