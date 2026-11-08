# I made some research on yt dlp from their docs but most of this will be done by ai I will disclose it
import sys
from pathlib import Path
 
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
 
DOWNLOADER = r'''import importlib.util
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
import app_settings
 
WINDOWS = sys.platform.startswith("win")
QUALITIES=app_settings.CHOICES["download_quality"]
SOURCES=("Youtube","Twitch","Rumble")
ACTIVE=("queued","downloading","processing")

for _d in ("/opt/homebrew/bin", "/usr/local/bin"):
    _parts = os.environ.get("PATH", "").split(os.pathsep)
    if os.path.isdir(_d) and _d not in _parts:
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + _d

JOBS={}
_WATCH={}
_LOCK = threading.RLock()
_SEM= threading.Semaphore(2)

def folder():
    p = Path.home() / "Downloads" / "Notifio"
    p.mkdir(parents=True, exist_ok=True)
    return p

def ffmpeg_path():
    root = Path(os.environ.get("NOTIFIO_ROOT", "."))
    bundled = root / "Assets" / ("ffmpeg.exe" if WINDOWS else "ffmpeg")
    if bundled.is_file():
        return str(bundled)
    return shutil.which("ffmpeg")

def status_text():
    if importlib.util.find_spec("yt_dlp")is None:
        return "yt-dlp is not installed.Run: pip3 install -U "yt-dlp[default]"'
    try:
        from importlib.metadata import version
        ver=version("yt-dlp")
    except Exception:
        ver="installed"
    bits = [f"yt-dlp {ver}"]
    if not ffmpeg_path():
        bits.append("ffmpeg missing: no merging, lower quality")
    if not shutil.which("deno"):
        bits.append("deno missing: YouTube may fail")


    
    