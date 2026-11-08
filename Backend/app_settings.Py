import shutil
import threading
import time
from pathlib import Path
from storage import get_data_dir, read_json, write_json

FILE = get_data_dir() / "settings.json"
LOCK = threading.RLock()

DEFAULTS = {
    "theme": "Dark",
    "accent": "Purple",
    "compact": False,
    "max_shown": 50,
    "poll_interval": 30,
    "notifications": True,
    "sound": True,
    "sound_file": "",
    "group_after": 3,
    "close_to_tray": True,
    "download_quality": "720p",
}

CHOICES = {
    "theme": ["Dark", "Midnight", "Light"],
    "accent": ["Purple", "Blue", "Green", "Orange", "Pink", "Red"],
    "max_shown": [25, 50, 100],
    "poll_interval": [15, 30, 60, 300],
    "group_after": [1, 3, 5, 10],
    "download_quality": ["Best", "1080p", "720p", "480p", "360p", "240p", "144p", "Audio only"],
}

_cache = None


def _sanitize(data):
    out = dict(DEFAULTS)
    if not isinstance(data, dict):
        return out
    for key, default in DEFAULTS.items():
        value = data.get(key, default)
        if key in CHOICES:
            if isinstance(value, bool) or value not in CHOICES[key]:
                value = default
        elif isinstance(default, bool) and not isinstance(value, bool):
            value = default
        elif isinstance(default, str) and not isinstance(value, str):
            value = default
        out[key] = value
    return out


def load():
    return _sanitize(read_json(FILE, {}))


def _current():
    global _cache
    with LOCK:
        if _cache is None:
            _cache = load()
        return _cache


def get(key):
    return _current().get(key, DEFAULTS.get(key))


def _write(data):
    global _cache
    clean = _sanitize(data)
    try:
        write_json(FILE, clean)
    except Exception:
        pass
    _cache = clean
    return clean


def set_value(key, value):
    with LOCK:
        if key in DEFAULTS:
            cur = dict(_current())
            cur[key] = value
            _write(cur)


def reset():
    with LOCK:
        return _write(dict(DEFAULTS))


def _store(path, prefix, default_suffix):
    if not path:
        return None
    try:
        src = Path(path)
        if not src.is_file():
            return None
        folder = get_data_dir()
        if src.parent.resolve() == folder.resolve() and src.name.startswith(prefix):
            return str(src)
        dest = folder / f"{prefix}-{int(time.time())}{src.suffix.lower() or default_suffix}"
        shutil.copy2(src, dest)
        for old in folder.glob(f"{prefix}*"):
            if old != dest:
                try:
                    old.unlink()
                except Exception:
                    pass
        return str(dest)
    except Exception:
        return str(path)


def store_avatar(path):
    return _store(path, "avatar", ".png")


def store_sound(path):
    return _store(path, "alert", ".mp3")