import threading
import traceback
import notifications
import notifier
from dexerto.feeds import FEEDS, fetch_all
from youtube.feeds import fetch_youtube, load_prefs,force_recheck
from twitch.feeds import fetch_twitch

SOURCES={
    **{name: (lambda feeds=feeds: fetch_all(feeds)) for name, feeds in FEEDS.items()},
    "Youtube":fetch_youtube,
    "Twitch":fetch_twitch,
}
KIND_TEXT={
    "video":"uploaded a new video",
    "short":"posted a new short",
    "live":"is LIVE now",
    "upcoming":"scheduled a live stream",
}
PREF_OF={"upcoming":"live"}
INTERVAL = 30
MAX_INDIVIDUAL = 3


class Poller:

    def __init__(self, plugins, on_update=None, interval=INTERVAL):
        self.plugins = [p for p in plugins if p in SOURCES]
        self.on_update = on_update
        self.interval = interval
        self._stop = threading.Event()
        self._wake = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def poll_now(self):
        force_recheck()
        self._wake.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception:
                traceback.print_exc()
            self._wake.wait(self.interval)
            self._wake.clear()

    def _poll(self):
        added = []
        to_ping = []
        failed = False
        for name in self.plugins:
            seeding = not notifications.has_seen(name)
            try:
                new = notifications.add_new(name, SOURCES[name]())
            except Exception:
                traceback.print_exc()
                failed = True
                continue
            added += new
            if not seeding:
                to_ping += new

        if self._stop.is_set():
            return
        fresh = self._filter(to_ping)
        self._ping(fresh)
        if self.on_update:
            self.on_update(added, failed, fresh)

    def _filter(self, items):
        if not items:
            return []
        wanted = load_prefs()
        out = []
        for i in items:
            kind = i.get("kind")
            if i.get("plugin")=="Youtube" and kind and PREF_OF.get(kind,kind) not in wanted:
                continue
            out.append(i)
        return out

    def _ping(self, items):
        if not items:
            return
        if len(items) > MAX_INDIVIDUAL:
            notifier.send("Notifio", f"{len(items)} new notifications")
            return
        for i in reversed(items):
            kind=i.get("kind")
            if kind:
                notifier.send(f'{i["source"]} {KIND_TEXT.get(kind, "posted")}', i["title"], i["link"])
            else:
                notifier.send(i["source"], i["title"], i["link"])