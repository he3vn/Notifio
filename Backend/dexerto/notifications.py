import json
from storage import get_data_dir

FILE= get_data_dir() / "notifications.json"
MAX_KEPT= 500

def load():
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return []

def save(items):
    try:
        FILE.write_text(json.dumps(items[:MAX_KEPT]))
    except Exception:
        pass

def add_new(plugin,fetched):
    history= load()
    known= {i["link"] for i in history}
    new=[]
    for item in fetched:
        if item["link"] and item["link"] not in known:
            new.append({**item, "plugin": plugin})
            known.add(item["link"])
    if new:
        history =sorted(new+ history, key=lambda i: i["ts"], reverse=True)
        save(history)
    return new
