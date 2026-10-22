import json, os
from pathlib import Path

FILE = Path(os.getenv("FLET_APP_STORAGE_DATA", Path(__file__).resolve().parent)) / "user.json"


def save_user(data: dict):
    existing = load_user() or {}
    existing.update(data)
    FILE.write_text(json.dumps(existing))


def load_user():
    return json.loads(FILE.read_text()) if FILE.exists() else None
