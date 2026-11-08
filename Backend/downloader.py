import importlib.util
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
QUALITIES = app_settings.CHOICES["download_quality"]
SOURCES = ("Youtube", "Twitch", "Rumble")
ACTIVE = ("queued", "downloading", "processing")


for _d in ("/opt/homebrew/bin", "/usr/local/bin"):
    _parts = os.environ.get("PATH", "").split(os.pathsep)
    if os.path.isdir(_d) and _d not in _parts:
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + _d

JOBS = {}
_WATCH = {}
_LOCK = threading.RLock()
_SEM = threading.Semaphore(2)


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
    if importlib.util.find_spec("yt_dlp") is None:
        return 'yt-dlp is not installed. Run: pip install -U "yt-dlp[default]"'
    try:
        from importlib.metadata import version
        ver = version("yt-dlp")
    except Exception:
        ver = "installed"
    bits = [f"yt-dlp {ver}"]
    if not ffmpeg_path():
        bits.append("ffmpeg missing: no merging, lower quality")
    if not shutil.which("deno"):
        bits.append("deno missing: YouTube may fail")
    return " | ".join(bits)


def can_download(item):
    if item.get("plugin") not in SOURCES or not item.get("link"):
        return False
    return item.get("kind") in (None, "video", "short")


def job(link):
    with _LOCK:
        j = JOBS.get(link)
        return dict(j) if j else None


def watch(link, fn):
    _WATCH[link] = fn


def clear_finished():
    with _LOCK:
        for k in [k for k, j in JOBS.items() if j["state"] not in ACTIVE]:
            JOBS.pop(k, None)


def _set(link, **kw):
    with _LOCK:
        j = JOBS.setdefault(link, {"state": "queued", "pct": 0.0, "speed": 0, "eta": None,
                                   "error": "", "file": "", "quality": ""})
        j.update(kw)
    fn = _WATCH.get(link)
    if fn:
        try:
            fn()
        except Exception:
            pass


def describe(j):
    """Short status text for a card."""
    st = j["state"]
    if st == "queued":
        return "Starting..."
    if st == "processing":
        return "Processing..."
    if st == "done":
        return "Saved"
    if st == "error":
        return j.get("error") or "Failed"
    bits = [f"{int(j['pct'] * 100)}%"]
    if j.get("speed"):
        bits.append(f"{j['speed'] / 1e6:.1f} MB/s")
    if j.get("eta") is not None:
        e = int(j["eta"])
        bits.append(f"{e // 60}:{e % 60:02d} left")
    return "  ".join(bits)

# I will let ai handle the rest for the formats might be a lot of converting
def format_for(q, has_ffmpeg):
    if q == "Audio only":
        return "ba/b" if has_ffmpeg else "ba[ext=m4a]/ba/b"
    if q == "Best":
        return "bv*+ba/b" if has_ffmpeg else "b"
    h = int(q[:-1])
    if has_ffmpeg:
        return f"bv*[height<={h}]+ba/b[height<={h}]/w"
    return f"b[height<={h}]/b"


def _clean(e):
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e))
    msg = msg.replace("ERROR: ", "").strip().splitlines()[-1] if msg.strip() else "Failed"
    return msg[:140]


def start(item, quality=None):
    """Queue a download. quality=None uses the default from settings."""
    link = item.get("link")
    if not link:
        return False
    q = quality if quality in QUALITIES else app_settings.get("download_quality")
    with _LOCK:
        j = JOBS.get(link)
        if j and j["state"] in ACTIVE:
            return False
        JOBS[link] = {"state": "queued", "pct": 0.0, "speed": 0, "eta": None,
                      "error": "", "file": "", "quality": q}
    _set(link, state="queued")
    threading.Thread(target=_run, args=(link, q), daemon=True).start()
    return True


def _final_path(info):
    try:
        rd = (info or {}).get("requested_downloads") or []
        if rd and rd[0].get("filepath"):
            return rd[0]["filepath"]
    except Exception:
        pass
    return ""


def _run(link, quality):
    with _SEM:
        _set(link, state="downloading", pct=0.0)
        try:
            import yt_dlp
        except Exception:
            _set(link, state="error", error="yt-dlp not installed (pip install -U yt-dlp)")
            return
        ff = ffmpeg_path()
        stage = {"n": 0, "last": 0.0}

        def hook(d):
            try:
                st = d.get("status")
                n = len((d.get("info_dict") or {}).get("requested_formats") or []) or 1
                if st == "finished":
                    stage["n"] += 1
                    return
                if st != "downloading":
                    return
                now = time.monotonic()
                if now - stage["last"] < 0.25:
                    return
                stage["last"] = now
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                if total:
                    p = done / total
                elif d.get("fragment_count"):
                    p = (d.get("fragment_index") or 0) / d["fragment_count"]
                else:
                    p = 0.0
                overall = min(0.99, (stage["n"] + min(p, 1.0)) / n)
                _set(link, state="downloading", pct=overall,
                     speed=d.get("speed") or 0, eta=d.get("eta"))
            except Exception:
                pass

        def pp_hook(d):
            if d.get("status") == "started":
                _set(link, state="processing", pct=1.0)

        opts = {
            "format": format_for(quality, bool(ff)),
            "format_sort": ["res", "ext:mp4:m4a"],
            "outtmpl": str(folder() / "%(title).120B [%(id)s].%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 5,
            "concurrent_fragment_downloads": 4,
            "progress_hooks": [hook],
            "postprocessor_hooks": [pp_hook],
        }
        if ff:
            opts["ffmpeg_location"] = ff
            opts["merge_output_format"] = "mp4"
            if quality == "Audio only":
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                           "preferredcodec": "mp3", "preferredquality": "192"}]
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
            _set(link, state="done", pct=1.0, file=_final_path(info))
        except Exception as e:
            traceback.print_exc()
            _set(link, state="error", error=_clean(e))


def _open_path(args):
    try:
        subprocess.Popen(args)
    except Exception:
        traceback.print_exc()


def open_folder():
    p = str(folder())
    if sys.platform == "darwin":
        _open_path(["open", p])
    elif WINDOWS:
        _open_path(["explorer", p])


def reveal(link):
    j = job(link)
    path = (j or {}).get("file")
    if not path or not Path(path).exists():
        open_folder()
        return
    if sys.platform == "darwin":
        _open_path(["open", "-R", path])
    elif WINDOWS:
        _open_path(["explorer", f"/select,{path}"])
