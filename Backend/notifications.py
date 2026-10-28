import json
from storage import get_data_dir

FILE= get_data_dir() / "notifications.json"
SEEN_FILE= get_data_dir() / "seen.json"
MAX_KEPT= 500
MAX_SEEN= 2000

def _read(path,default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def _write(path,data):
    try:
        path.write_text(json.dumps(data))
    except Exception:
        pass

def load():
    return _read(FILE,[])

def save(items):
    _write(FILE,items[:MAX_KEPT])

def _load_seen():
    seen= _read(SEEN_FILE,{})
    return seen if isinstance(seen,dict)else {}

def has_seen(plugin):
    return bool(_load_seen().get(plugin)) or any (i.get("plugin")== plugin for i in load())

def add_new(plugin,fetched):
    history= load()
    seen=_load_seen()
    known= set(seen.get(plugin,[]))| {i["link"] for i in history}
    new=[]
    for item in fetched:
        if item["link"] and item["link"] not in known:
            new.append({**item, "plugin": plugin})
            known.add(item["link"])
    if new:
        save(sorted(new+history,key=lambda i:i["ts"],reverse=True))
        seen[plugin] = ([i["link"] for i in new] + seen.get(plugin, []))[:MAX_SEEN]
        _write(SEEN_FILE,seen)
    return new

def remove(link):
    history=load()
    seen=_load_seen()
    for i in history:
        if i["link"] == link:
            mine=seen.setdefault(i.get("plugin","?"),[])
            if link not in mine:
                mine.insert(0,link)
    _write(SEEN_FILE,seen)
    save([i for i in history if i["link"] != link])

def clear_all():
    history=load()
    seen=_load_seen()
    by_plugin={}
    for i in history:
        by_plugin.setdefault(i.get("plugin","?"),[]).append(i["link"])
    for plugin, links in by_plugin.items():
        mine=seen.get(plugin,[])
        seen[plugin]=(links+[l for l in mine if l not in links])[:MAX_SEEN]
    _write(SEEN_FILE,seen)
    save([])


    