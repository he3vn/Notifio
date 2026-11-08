"""Delete Notifio's local history and channel list, then restart setup."""
import traceback
from pathlib import Path

import app_settings
import control
import notifications
from storage import get_data_dir

DATA_FILES = (
    "notifications.json", "seen.json", "user.json", "user_setup.json",
    "selected_plugins.json", "youtube_channels.json", "youtube_prefs.json",
    "twitch_channels.json", "rumble_channels.json", "settings.json",
    "downloads.json", "missed.json",
)


def _rm(path):
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
    except Exception:
        traceback.print_exc()


def wipe():
    folder = get_data_dir()
    with notifications.LOCK:
        for name in DATA_FILES:
            _rm(folder / name)
        for p in folder.iterdir():
            if p.is_file() and p.name.startswith(("avatar", "alert")):
                _rm(p)
        notifications.LOST = True
        notifications.RESTORED.clear()

    try:
        control.clear_missed()
    except Exception:
        traceback.print_exc()

    app_settings._cache = None
    notifications.RESTORED.clear()
    try:
        import downloader
        downloader.clear_finished()
    except Exception:
        traceback.print_exc()
