import json, os
from pathlib import Path


def get_data_dir() -> Path:
    p = Path(os.getenv("FLET_APP_STORAGE_DATA", Path.home() / ".notifio"))
    p.mkdir(parents=True, exist_ok=True)
    return p


FILE = get_data_dir() / "user.json"


def save_user(data: dict):
    existing = load_user() or {}
    existing.update(data)
    FILE.write_text(json.dumps(existing))


def load_user():
    return json.loads(FILE.read_text()) if FILE.exists() else None
