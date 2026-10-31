import html,re,threading,time,urllib.request,urllib.error
import notifications
from storage import get_data_dir,read_json, write_json
from dexerto.feeds import _ssl_context,_timestamp

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
FILE=get_data_dir() /"rumble_channels.json"
LOCK=threading.RLock()
NAME_RE= re.compile(r"[A-Za-z0-9_\-]{2,60}")

def load_channels():
    with LOCK:
        data= read_json(FILE,[])
        return data if isinstance(data,list) else []

def _save_channels(chs):
    with LOCK:
        write_json(FILE,chs)

def _page(path):
    req=urllib.request.Request(f"https://rumble.com/{path}",headers={"User-Agent": UA})
    with urllib.request.urlopen(req,timeout=10,context=_ssl_context()) as r:
        return r.read(3_000_000).decode("utf-8","ignore")

def parse_chanel(text):
    t=text.strip()
    m=re.search(r"rumble\.com/(c|user)/([A-Za-z0-9_\-]+)", t)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    name=t.lstrip("@/ ")
    if not NAME_RE.fullmatch(name):
        raise ValueError("Enter a channel name or rumble URL")
    return f"c/{name}"

def _parse(page,channel):
    items=[]
    for chunk in page.split("videostream thumbnail__grid--item")[1:]:
        link=re.search(r'href="(/v[\w\-]+\.html)',chunk)
        title=re.search(r'thumbnail__title[^>]*?title="([^"]+)"',chunk) \
            or re.search(r'thumbnail__title[^>]*>\s*([^<]+)', chunk)
        if not link or not title: continue
        when=re.search(r'<time[^>]*datetime="([^"]+)"',chunk)
        live="videostream__status--live" in chunk
        items.append({
            "title":html.unescape(title.group(1)).strip(),
            "link": "https://rumble.com"+ link.group(1),
            "ts":(_timestamp(when.group(1)) if when else 0) or time.time(),
            "source": channel["name"],
            "channel_id": channel["id"],
            "kind": "live" if live else "video",
        })
    return items

def add_channel(text):
    cid=parse_chanel(text)
    if any(c["id"] == cid for c in load_channels()): raise ValueError("already added")
    try: page= _page(cid)
    except urllib.error.HTTPError as e: raise ValueError("no channel with that name" if e.code==404 else f"HTTP {e.code}")
    t=re.search(r'<meta property="og:title" content="([^"]+)"', page) or re.search(r"<title>([^<]+)</title>", page)
    name=html.unescape(t.group(1)).split(" - ")[0].strip() if t else cid.split("/")[-1]
    ch={"id": cid, "name":name}
    items= _parse(page,ch)
    if not items: raise ValueError("couldnt read videos from that page")
    notifications.add_new("Rumble",items)
    with LOCK:
        chs=load_channels()
        if not any(c["id"]==cid for c in chs):
            _save_channels(chs+[ch])
    return ch

def remove_channel(cid):
    _save_channels([c for c in load_channels() if c["id"] != cid])
    for i in notifications.load():
        if i.get("plugin")== "Rumble" and i.get("channel_id")==cid:
            notifications.remove(i["link"])

def fetch_rumble():
    channels=load_channels()
    if not channels:
        return []
    items=[]
    failed=0
    err=None
    for ch in channels:
        try: items +=_parse(_page(ch["id"]), ch)
        except Exception as e: failed,err=failed +1,e
    if not items and failed: raise RuntimeError(f"all channels failed: {err!r}")
    items.sort(key=lambda i: i["ts"],reverse=True)
    return items [:100]


