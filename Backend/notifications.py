import json
from storage import get_data_dir

FILE = get_data_dir() / "notifications.json"
SEEN_FILE = get_data_dir() / "seen.json"
MAX_KEPT = 500
MAX_SEEN = 2000


def _read(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _write(path, data):
    try:
        path.write_text(json.dumps(data))
    except Exception:
        pass


def load():
    return _read(FILE, [])


def save(items):
    _write(FILE, items[:MAX_KEPT])


def _load_seen():
    seen = _read(SEEN_FILE, {})
    return seen if isinstance(seen, dict) else {}


def has_seen(plugin):
    return bool(_load_seen().get(plugin)) or any(i.get("plugin") == plugin for i in load())


def add_new(plugin, fetched):
    history = load()
    seen = _load_seen()
    history_links = {i["link"] for i in history}
    seen_links = set(seen.get(plugin, []))
    known = seen_links | history_links
    new = []
    for item in fetched:
        if item["link"] and item["link"] not in known:
            new.append({**item, "plugin": plugin})
            known.add(item["link"])

    # Items that were in seen (e.g. after clear_all) but not in history anymore
    # should be re-added to the visible list so the UI isn't empty
    restored = []
    if not history_links:
        for item in fetched:
            if item["link"] and item["link"] in seen_links and item["link"] not in history_links:
                restored.append({**item, "plugin": plugin})

    to_save = new + restored + history
    if new or restored:
        save(sorted(to_save, key=lambda i: i["ts"], reverse=True))
        seen[plugin] = ([i["link"] for i in new] + seen.get(plugin, []))[:MAX_SEEN]
        _write(SEEN_FILE, seen)
    # Only return genuinely new items (restored ones don't trigger a ping)
    return new


def remove(link):
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
