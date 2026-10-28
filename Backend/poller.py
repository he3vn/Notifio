import threading
import notifications
import notifier
import traceback
from dexerto.feeds import FEEDS, fetch_all

INTERVAL = 300
MAX_INDIVIDUAL= 3

class Poller:

    def __init__(self, plugins,on_update=None,interval=INTERVAL):
        self.plugins= [p for p in plugins if p in FEEDS]
        self.on_update=on_update
        self.interval=interval
        self._stop= threading.Event()
        self._wake=threading.Event()

    def start(self):
        threading.Thread(target=self._loop,daemon=True).start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def poll_now(self):
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
                new = notifications.add_new(name, fetch_all(FEEDS[name]))
            except Exception:
                failed = True
                continue
            added += new
            if not seeding:
                to_ping += new

        if self._stop.is_set():
            return
        self._ping(to_ping)
        if self.on_update:
            self.on_update(added, failed)

    def _ping(self,items):
        if not items:
            return
        if len(items)>MAX_INDIVIDUAL:
            notifier.send("Notifio",f"{len(items)} new notifications")
            return
        for i in reversed(items):
            notifier.send(i["source"], i["title"], i["link"])
