import importlib.util
import json
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
from storage import get_data_dir, read_json, write_json

WINDOWS = sys.platform.startswith("win")
QUALITIES = app_settings.CHOICES["download_quality"]
SOURCES = ("Youtube", "Twitch", "Rumble")
ACTIVE = ("queued", "downloading", "processing")
DOWNLOADABLE_KINDS = (None, "video", "short", "live", "upcoming")

PENDING_FILE = get_data_dir() / "downloads.json"


# Make Homebrew / common package-manager tools visible when the app is
# launched from Finder or the Start menu (where PATH is very small).
_PATH_DIRS = ["/opt/homebrew/bin", "/usr/local/bin"]
if WINDOWS:
    _PATH_DIRS += [
        str(Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "chocolatey" / "bin"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"),
    ]
for _d in _PATH_DIRS:
    _parts = os.environ.get("PATH", "").split(os.pathsep)
    if _d and os.path.isdir(_d) and _d not in _parts:
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + _d

JOBS = {}
_WATCH = {}
_LOCK = threading.RLock()
_SEM = threading.Semaphore(2)

# Codecs that QuickTime / Windows Media Player can play inside an MP4 without
# installing extra codec packs.  Anything else gets re-encoded.
VIDEO_OK = {"h264", "hevc"}
AUDIO_OK = {"aac", "mp3", "alac"}


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


def ffprobe_path(ff):
    if ff:
        p = Path(ff)
        sibling = p.with_name("ffprobe.exe" if p.suffix.lower() == ".exe" else "ffprobe")
        if sibling.is_file():
            return str(sibling)
    return shutil.which("ffprobe")


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
        bits.append("ffmpeg missing: no merging or QuickTime fix")
    if not shutil.which("deno"):
        bits.append("deno missing: YouTube may fail")
    return " | ".join(bits)


def can_download(item):
    if item.get("plugin") not in SOURCES or not item.get("link"):
        return False
    return item.get("kind") in DOWNLOADABLE_KINDS


def job(link):
    with _LOCK:
        j = JOBS.get(link)
        return dict(j) if j else None


def watch(link, fn):
    _WATCH[link] = fn


def unwatch(link):
    _WATCH.pop(link, None)


def clear_finished():
    with _LOCK:
        for k in [k for k, j in JOBS.items() if j["state"] not in ACTIVE]:
            JOBS.pop(k, None)


def _set(link, **kw):
    terminal = False
    with _LOCK:
        j = JOBS.setdefault(link, {"state": "queued", "pct": 0.0, "speed": 0, "eta": None,
                                   "error": "", "file": "", "quality": "", "item": {"link": link}})
        j.update(kw)
        terminal = j.get("state") not in ACTIVE
    if terminal:
        _pending_drop(link)
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


def _yt_format(q, has_ffmpeg):
    """Prefer H.264 + AAC in MP4 so the result opens in QuickTime/Windows.

    The fallbacks still let yt-dlp grab the best available stream when a
    compatible one does not exist; _ensure_compatible then re-encodes it.
    """
    if q == "Audio only":
        return "ba[ext=m4a]/ba/b"
    if not has_ffmpeg:
        if q == "Best":
            return "b[ext=mp4][vcodec^=avc1]/b[ext=mp4]/b"
        h = int(q[:-1])
        return f"b[height<={h}][ext=mp4][vcodec^=avc1]/b[height<={h}]/b"

    height = None if q == "Best" else int(q[:-1])
    hv = f"[height<={height}]" if height else ""
    bv = f"b{hv}"
    return "/".join([
        f"bv*{hv}[vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a][ext=m4a]",
        f"{bv}[ext=mp4][vcodec^=avc1]",
        f"bv*{hv}[ext=mp4]+ba[ext=m4a]",
        f"bv*{hv}+ba",
        f"{bv}/w",
    ])


# yt-dlp's format string treats spaces literally, so keep the helper output clean.
def format_for(q, has_ffmpeg):
    return _yt_format(q, has_ffmpeg).replace(" ", "")


def _clean(e):
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e))
    msg = msg.replace("ERROR: ", "").strip().splitlines()[-1] if msg.strip() else "Failed"
    return msg[:140]


def _clean_item(item):
    return {
        k: item.get(k)
        for k in ("link", "plugin", "kind", "title", "source", "channel_id")
        if item.get(k) is not None
    }


def _pending_snapshot():
    with _LOCK:
        return [
            {"link": link, "quality": j.get("quality"), "item": j.get("item") or {"link": link}}
            for link, j in JOBS.items()
            if j.get("state") in ACTIVE and link
        ]


def _pending_save():
    try:
        write_json(PENDING_FILE, _pending_snapshot())
    except Exception:
        traceback.print_exc()


def _pending_drop(link):
    try:
        data = read_json(PENDING_FILE, [])
        if not isinstance(data, list):
            return
        write_json(PENDING_FILE, [
            r for r in data if not (isinstance(r, dict) and r.get("link") == link)
        ])
    except Exception:
        traceback.print_exc()


def resume_pending():
    """Requeue downloads that were still running when the app closed/crashed."""
    data = read_json(PENDING_FILE, [])
    if not isinstance(data, list):
        return 0
    resumed = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        link = rec.get("link")
        if not link:
            continue
        item = rec.get("item")
        if not isinstance(item, dict):
            item = {"link": link}
        item.setdefault("link", link)
        quality = rec.get("quality")
        if quality not in QUALITIES:
            quality = None
        if _start(item, quality, persist=False):
            resumed += 1
    _pending_save()
    return resumed


def start(item, quality=None):
    """Queue a download. quality=None uses the default from settings."""
    return _start(item, quality, persist=True)


def _start(item, quality=None, persist=True):
    link = item.get("link")
    if not link:
        return False
    q = quality if quality in QUALITIES else app_settings.get("download_quality")
    with _LOCK:
        j = JOBS.get(link)
        if j and j["state"] in ACTIVE:
            return False
        JOBS[link] = {"state": "queued", "pct": 0.0, "speed": 0, "eta": None,
                      "error": "", "file": "", "quality": q, "item": _clean_item(item)}
    if persist:
        _pending_save()
    _set(link, state="queued")
    threading.Thread(target=_run, args=(link, q), daemon=True).start()
    return True


def _final_path(info):
    try:
        rd = (info or {}).get("requested_downloads") or []
        if rd and rd[0].get("filepath"):
            return rd[0]["filepath"]
        for key in ("filepath", "_filename"):
            if (info or {}).get(key):
                return info[key]
    except Exception:
        pass
    return ""


def _run_hidden(cmd, timeout=None):
    kwargs = {}
    if WINDOWS:
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kwargs)


def _probe(path, ff):
    probe = ffprobe_path(ff)
    if not probe:
        return None
    try:
        r = _run_hidden(
            [probe, "-v", "error", "-show_entries", "stream=codec_type,codec_name",
             "-of", "json", str(path)],
            timeout=60,
        )
        data = json.loads(r.stdout or "{}")
    except Exception:
        return None
    video = audio = None
    for s in data.get("streams") or []:
        kind = s.get("codec_type")
        if kind == "video" and not video:
            video = s.get("codec_name")
        elif kind == "audio" and not audio:
            audio = s.get("codec_name")
    return video, audio


def _out_path(src):
    src = Path(src)
    out = src.with_suffix(".mp4")
    if out.resolve() == src.resolve():
        out = src.with_name(src.stem + "-fixed.mp4")
    base = out
    n = 2
    while out.exists():
        out = base.with_name(f"{base.stem}-{n}.mp4")
        n += 1
    return out


def _run_ffmpeg(cmd):
    try:
        r = _run_hidden(cmd)
    except Exception:
        traceback.print_exc()
        return False
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()[-1:] or ["ffmpeg failed"]
        print(f"downloader: {tail[0]}", file=sys.stderr)
        return False
    return True


def _remux(src, out, ff, audio):
    base = [ff, "-y", "-i", str(src), "-c", "copy"]
    # Older TS streams carry ADTS AAC; this bitstream filter rewrites it into
    # the duration-based AAC that MP4/QuickTime expects.
    if str(src).lower().endswith((".ts", ".m2ts")) and audio in (None, "aac"):
        cmd = base + ["-bsf:a", "aac_adtstoasc", "-movflags", "+faststart", str(out)]
        if _run_ffmpeg(cmd):
            return True
    cmd = base + ["-movflags", "+faststart", str(out)]
    return _run_ffmpeg(cmd)


def _transcode(src, out, ff):
    cmd = [
        ff, "-y", "-i", str(src),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(out),
    ]
    if _run_ffmpeg(cmd):
        return True
    # Some ffmpeg builds ship without libx264. Copying the video is not ideal,
    # but it is still better than leaving a file that cannot be opened.
    cmd = [ff, "-y", "-i", str(src), "-c:v", "copy", "-c:a", "aac",
           "-movflags", "+faststart", str(out)]
    return _run_ffmpeg(cmd)


def _ensure_compatible(path, ff):
    """Return a path to an MP4 that normal players (QuickTime, Windows) accept."""
    if not path:
        return path
    src = Path(path)
    if not src.is_file() or not ff:
        return path

    codecs = _probe(src, ff)
    compatible = True
    audio = None
    if codecs:
        video, audio = codecs
        compatible = (not video or video in VIDEO_OK) and (not audio or audio in AUDIO_OK)

    if src.suffix.lower() in (".mp4", ".m4v", ".mov") and compatible:
        return path

    out = _out_path(src)
    ok = _transcode(src, out, ff) if not compatible else _remux(src, out, ff, audio)
    if not ok:
        return path

    # We just produced a fresh compatible MP4, so drop the old container.
    if src.resolve() != out.resolve():
        try:
            src.unlink()
        except Exception:
            pass
    return str(out)


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
            "format_sort": ["vcodec:h264", "acodec:aac", "res", "ext:mp4:m4a"],
            "outtmpl": str(folder() / "%(title).120B [%(id)s].%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 10,
            "fragment_retries": 10,
            "concurrent_fragment_downloads": 4,
            "continuedl": True,
            "nopart": False,
            "overwrites": False,
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
            final = _final_path(info)
            if quality != "Audio only":
                _set(link, state="processing", pct=1.0)
                try:
                    final = _ensure_compatible(final, ff)
                except Exception:
                    traceback.print_exc()
            _set(link, state="done", pct=1.0, file=final)
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
