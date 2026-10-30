import json, os, threading
from pathlib import Path

LOCK = threading.Lock()


def get_data_dir() -> Path:
    p = Path(os.getenv("FLET_APP_STORAGE_DATA", Path.home() / ".notifio"))
    p.mkdir(parents=True, exist_ok=True)
    return p


FILE = get_data_dir() / "user.json"


def read_json(path, default=None):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except Exception:
        try: os.replace(path, path.with_name(path.name + ".corrupt"))
        except Exception: pass
        return default


def write_json(path, data):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with LOCK:
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, path)


def save_user(data: dict):
    existing = load_user() or {}
    existing.update(data)
    write_json(FILE, existing)


def load_user():
    return read_json(FILE, None)