import threading
import traceback
from storage import get_data_dir, read_json, write_json

FILE = get_data_dir() / "notifications.json"
SEEN_FILE = get_data_dir() / "seen.json"
MAX_KEPT = 500
MAX_SEEN = 2000
LOCK = threading.RLock()
LOST = not FILE.exists()
RESTORED = set()


def _read(path, default):
    return read_json(path, default)


def _write(path, data):
    try:
        write_json(path, data)
    except Exception:
        traceback.print_exc()


def load():
    with LOCK:
        data = _read(FILE, [])
        return data if isinstance(data, list) else []


def save(items):
    with LOCK:
        _write(FILE, items[:MAX_KEPT])


def _load_seen():
    seen = _read(SEEN_FILE, {})
    return seen if isinstance(seen, dict) else {}

def known_links(plugin):
    with LOCK:
        return {i["link"] for i in load()} | set(_load_seen().get(plugin, []))

def has_seen(plugin):
    with LOCK:
        return plugin in _load_seen() or any(i.get("plugin") == plugin for i in load())


def add_new(plugin, fetched):
    with LOCK:
        history = load()
        seen = _load_seen()
        first = plugin not in seen
        history_links = {i["link"] for i in history}
        seen_links = set(seen.get(plugin, []))
        known = seen_links | history_links
        new = []
        for item in fetched:
            if item["link"] and item["link"] not in known:
                new.append({**item, "plugin": plugin})
                known.add(item["link"])

        restored = []
        if LOST and plugin not in RESTORED:
            RESTORED.add(plugin)
            for item in fetched:
                if item["link"] and item["link"] in seen_links and item["link"] not in history_links:
                    restored.append({**item, "plugin": plugin})

        if first:
            seen[plugin] = []
        if new or restored:
            save(sorted(new + restored + history, key=lambda i: i["ts"], reverse=True))
            seen[plugin] = ([i["link"] for i in new] + seen.get(plugin, []))[:MAX_SEEN]
        if new or restored or first:
            _write(SEEN_FILE, seen)
        return new


def remove(link):
    with LOCK:
        history = load()
        seen = _load_seen()
        for i in history:
            if i["link"] == link:
                mine = seen.setdefault(i.get("plugin", "?"), [])
                if link not in mine:
                    mine.insert(0, link)
        _write(SEEN_FILE, seen)
        save([i for i in history if i["link"] != link])


def clear_all():
    with LOCK:
        history = load()
        seen = _load_seen()
        by_plugin = {}
        for i in history:
            by_plugin.setdefault(i.get("plugin", "?"), []).append(i["link"])
        for plugin, links in by_plugin.items():
            mine = seen.get(plugin, [])
            seen[plugin] = (links + [l for l in mine if l not in links])[:MAX_SEEN]
        _write(SEEN_FILE, seen)
        save([])