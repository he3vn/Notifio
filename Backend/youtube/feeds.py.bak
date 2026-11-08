import re,threading,urllib.request,urllib.error
import xml.etree.ElementTree as ET
import time
import notifications
from storage import get_data_dir,read_json,write_json
from dexerto.feeds import _ssl_context,_timestamp

ATOM="{http://www.w3.org/2005/Atom}"
YT="{http://www.youtube.com/xml/schemas/2015}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
FILE=get_data_dir() /"youtube_channels.json"
PREFS_FILE=get_data_dir() /"youtube_prefs.json"
VALID_TYPES=["video", "short", "live"]
DEFAULT_TYPES=["video", "short", "live"]
CLASSIFY_LIMIT= 15
RECHECK_EVERY=60
_last_recheck=0

LOCK=threading.RLock()

def load_prefs():
    data=read_json(PREFS_FILE,None)
    if isinstance(data,list): return [t for t in data if t in VALID_TYPES]
    return list(DEFAULT_TYPES)

def save_prefs(types):
    write_json(PREFS_FILE,[t for t in VALID_TYPES if t in types])

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):
        return None

def _open(url,timeout=8,follow=True):
    req=urllib.request.Request(url,headers={"User-Agent": UA})
    ctx=_ssl_context()
    if follow:
        return urllib.request.urlopen(req,timeout=timeout,context=ctx)
    opener=urllib.request.build_opener(_NoRedirect,urllib.request.HTTPSHandler(context=ctx))
    return opener.open(req,timeout=timeout)

def load_channels():
    with LOCK:
        data=read_json(FILE,[])
        return data if isinstance(data,list) else []

def _save_channels(chs):
    with LOCK:
        write_json(FILE,chs)

def resolve_channel_id(text):
    text=text.strip()
    m=re.search(r"(UC[\w-]{22})", text)
    if m and (text.startswith("UC") or "channel/" in text):
        return m.group(1)
    m=re.search(r"@([\w.\-]+)", text)
    handle=m.group(1) if m else text.lstrip("@/ ")
    if not re.fullmatch(r"[\w.\-]+", handle):
        raise ValueError("enter a @handle or channel URL")
    try:
        with _open(f"https://www.youtube.com/@{handle}") as r:
            page=r.read(2_000_000).decode("utf-8","ignore")
    except urllib.error.HTTPError as e:
        raise ValueError("no channel with that handle" if e.code==404 else f"HTTP {e.code}")
    m = (re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', page)
         or re.search(r'"externalId":"(UC[\w-]{22})"', page)
         or re.search(r'"channelId":"(UC[\w-]{22})"', page))
    if not m:
        raise ValueError("couldn't find that channel")
    return m.group(1)

def add_channel(text):
    cid=resolve_channel_id(text)
    if any(c["id"] == cid for c in load_channels()):
        raise ValueError("already added")
    root = _feed_root(cid)
    ch={"id": cid, "name":(root.findtext(ATOM+"title")or cid).strip()}
    items=_parse(root,ch,known=notifications.known_links("Youtube"))
    notifications.add_new("Youtube",items)
    with LOCK:
        chs=load_channels()
        if not any(c["id"]==cid for c in chs):
            _save_channels(chs+[ch])
    if "live" in load_prefs():
        for it in items:
            if it.get("kind") == "live":
                import notifier
                notifier.send(f'{ch["name"]} is LIVE now', it["title"], it["link"])
                break
    return ch

def remove_channel(cid):
    _save_channels([c for c in load_channels() if c["id"] !=cid])
    for i in notifications.load():
        if i.get("plugin")== "Youtube" and i.get("channel_id")==cid:
            notifications.remove(i["link"])


def _is_short(vid):
    try:
         with _open(f"https://www.youtube.com/shorts/{vid}", follow=False) as r:
             return r.status ==200
    except urllib.error.HTTPError: return False
    except Exception: return None

def _watch_page(vid):
    try:
        with _open(f"https://www.youtube.com/watch?v={vid}",timeout=10)as r:
            return r.read(3_000_000).decode("utf-8","ignore")
    except Exception: return None

def _state_from_page(page):
    if '"isLive":true' in page:
        return "live"
    if '"isUpcoming":true' in page:
        return "upcoming"
    return None

def _live_state(vid):
    page=_watch_page(vid)
    return _state_from_page(page) if page else None

def classify(vid):
    if _is_short(vid) is True:
        return "short"
    return _live_state(vid) or "video"

_ROOTS={}
def _feed_root(cid):
    with _open(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}") as r:
        return ET.fromstring(r.read())

def _parse(root,ch,known):
    items,classified=[],0
    for en in root.iter(ATOM+"entry"):
        vid=en.findtext(YT+"videoId")
        if not vid:
            continue
        link=f"https://www.youtube.com/watch?v={vid}"
        kind="video"
        if link not in known and classified<CLASSIFY_LIMIT:
            kind=classify(vid)
            classified +=1
        items.append({
            "title": (en.findtext(ATOM + "title") or "").strip(),
            "link":link,
            "ts": _timestamp(en.findtext(ATOM+"published")),
            "source":ch["name"],
            "channel_id":ch["id"],
            "kind":kind,
        })
    return items

def fetch_youtube():
    channels=load_channels()
    if not channels:
        return []
    known=notifications.known_links("Youtube")
    items=[]
    failed=0
    err=None
    for ch in channels:
        try:
            items += _parse(_feed_root(ch["id"]),ch,known)
        except Exception as e: failed,err=failed +1,e
    if not items and failed:
        raise RuntimeError(f"all channels failed:{err!r}")
    items.sort(key=lambda i: i["ts"],reverse=True)
    _recheck_lives()
    return items[:100]

def _recheck_lives():
    global _last_recheck
    if time.time()- _last_recheck < RECHECK_EVERY:
        return
    _last_recheck=time.time()
    candidates=[]
    for item in notifications.load():
        if item.get("plugin") != "Youtube":
            continue
        if item.get("kind") not in ("upcoming", None):
            continue
        link=item.get("link","")
        if "v=" not in link:
            continue
        candidates.append(link)
        if len(candidates)>=3:
            break
    if not candidates:
        return

    updates={}
    for link in candidates:
        page=_watch_page(link.split("v=")[-1])
        if page is None:
            continue
        state=_state_from_page(page)
        if state=="live":
            updates[link]="live"
        elif state is None:
            updates[link]="video"
    if not updates:
        return

    newly_live = []
    with notifications.LOCK:
        history=notifications.load()
        changed=False
        for item in history:
            new_kind=updates.get(item.get("link"))
            if new_kind and item.get("kind")!=new_kind:
                if new_kind == "live":
                    newly_live.append(item)
                item["kind"]=new_kind
                changed=True
        if changed:
            notifications.save(history)

    if newly_live and "live" in load_prefs():
        import notifier
        for item in newly_live:
            notifier.send(f'{item["source"]} is LIVE now', item["title"], item["link"])

def force_recheck():
    global _last_recheck
    _last_recheck=0