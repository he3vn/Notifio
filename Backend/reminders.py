"""Periodic "check your notifications" reminders.

The reminder only fires when something arrived after the last time the user
looked at the app, so it never nags about old history.  Notifications are
delivered through the normal notifier (terminal-notifier / UNUserNotificationCenter
on macOS, winotify on Windows).
"""
import threading
import time
import traceback

import app_settings
import notifications

CHECK_EVERY = 15.0  # seconds; cheap comparison against the local history file
_last_ping = 0.0
_started = False
_lock = threading.Lock()


def _settings():
    try:
        every = int(app_settings.get("reminder_interval") or 30)
    except (TypeError, ValueError):
        every = 30
    if every <= 0:
        every = 30
    try:
        seen = float(app_settings.get("last_seen_ts") or 0)
    except (TypeError, ValueError):
        seen = 0.0
    return bool(app_settings.get("reminder")), every * 60.0, seen


def mark_seen():
    """Remember that the user has looked at the notification centre."""
    app_settings.set_value("last_seen_ts", time.time())


def pending_count():
    """Number of history items newer than the last time the app was viewed."""
    _, _, seen = _settings()
    count = 0
    for item in notifications.load():
        try:
            stamp = item.get("_added")
            if stamp is None:
                stamp = item.get("ts") or 0
            if float(stamp) > seen:
                count += 1
        except (TypeError, ValueError):
            continue
    return count


def _due(now):
    enabled, interval, seen = _settings()
    if not enabled or not seen:
        return False
    if now - _last_ping < interval:
        return False
    return pending_count() > 0


def _loop():
    global _last_ping
    while True:
        try:
            now = time.time()
            if _due(now):
                _last_ping = now
                import notifier
                notifier.send("Notifio", "Check your notifications gng")
        except Exception:
            traceback.print_exc()
        time.sleep(CHECK_EVERY)


def start():
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, name="notifio-reminders", daemon=True).start()


def test():
    import notifier
    notifier.send("Notifio", "Check your notifications gng")
