import html, json, re, subprocess, threading, time, urllib.request, urllib.error
import notifications
from storage import get_data_dir, read_json, write_json
from dexerto.feeds import _ssl_context, _timestamp

try:
    from curl_cffi import requests as cffi
except Exception:
    cffi = None

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
FILE = get_data_dir() / "rumble_channels.json"
LOCK = threading.RLock()
NAME_RE = re.compile(r"[A-Za-z0-9_\-]{2,60}")
CHANNEL_MARKERS = (
    "channel-header--title", "channel-header--content",
    "listing-header--content", "channel-header--img",
)
VIDEO_MARKER = '{"object_type":"video"'


def load_channels():
    with LOCK:
        data = read_json(FILE, [])
        return data if isinstance(data, list) else []


def _save_channels(chs):
    with LOCK:
        write_json(FILE, chs)


def _impersonate(url):
    r = cffi.get(url, impersonate="chrome", timeout=15,
                 headers={"Accept-Language": "en-US,en;q=0.9"})
    if r.status_code >= 400:
        raise urllib.error.HTTPError(url, r.status_code, "blocked", None, None)
    return r.text


def _curl(url):
    cmd = ["curl", "-sL", "--compressed", "--max-time", "12", "-w", "\n%{http_code}"]
    for k, v in HEADERS.items():
        cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd + [url], capture_output=True, timeout=15)
    body, _, code = r.stdout.decode("utf-8", "ignore").rpartition("\n")
    code = int(code) if code.isdigit() else 0
    if code == 0 or code >= 400:
        raise urllib.error.HTTPError(url, code or 599, "curl failed", None, None)
    return body


def _page(path):
    url = f"https://rumble.com/{path}"
    if cffi:
        try:
            return _impersonate(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
        except Exception:
            pass
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as r:
            return r.read(3_000_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
    return _curl(url)


def parse_channel(text):
    t = text.strip()
    m = re.search(r"rumble\.com/(c|user)/([A-Za-z0-9_\-]+)", t)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    name = t.lstrip("@/ ")
    if not NAME_RE.fullmatch(name):
        raise ValueError("Enter a channel name or rumble URL")
    return f"c/{name}"


def _check_page(page):
    if not any(m in page for m in CHANNEL_MARKERS):
        raise ValueError("page doesn't look like a Rumble channel (blocked or markup changed)")


def _videos(page, cid):
    """Video objects embedded as JSON in the page, only those posted by this channel."""
    _check_page(page)
    want = cid.split("/")[-1].lower()
    dec = json.JSONDecoder()
    out, seen, pos = [], set(), 0
    while True:
        i = page.find(VIDEO_MARKER, pos)
        if i == -1:
            break
        pos = i + len(VIDEO_MARKER)
        try:
            obj, end = dec.raw_decode(page, i)
        except ValueError:
            continue
        pos = end
        by = obj.get("by") or {}
        slug = (by.get("relative_url") or "").rstrip("/").split("/")[-1].lower()
        url = (obj.get("url") or "").split("?")[0]
        if slug != want or not url or url in seen:
            continue
        seen.add(url)
        out.append(obj)
    return out


def _fetch_objs(cid):
    page = _page(cid)
    objs = _videos(page, cid)
    if not objs:
        try:
            page2 = _page(cid + "/videos")
            objs = _videos(page2, cid)
        except Exception:
            pass
    return page, objs


def _items(objs, channel):
    items = []
    for o in objs:
        title = (o.get("title") or "").strip()
        url = (o.get("url") or "").split("?")[0]
        if not title or not url:
            continue
        live = bool(o.get("live"))
        kind = "live" if live else ("short" if o.get("is_short") else "video")
        when = o.get("upload_date") or o.get("live_datetime")
        items.append({
            "title": title,
            "link": url,
            "ts": _timestamp(when) or time.time(),
            "source": channel["name"],
            "channel_id": channel["id"],
            "kind": kind,
        })
    return items


def add_channel(text):
    cid = parse_channel(text)
    if any(c["id"] == cid for c in load_channels()):
        raise ValueError("already added")
    try:
        page, objs = _fetch_objs(cid)
    except urllib.error.HTTPError as e:
        raise ValueError("no channel with that name" if e.code == 404 else f"HTTP {e.code}")
    name = None
    if objs:
        name = (objs[0].get("by") or {}).get("name")
    if not name:
        t = (re.search(r"<h1[^>]*>\s*([^<]+?)\s*</h1>", page)
             or re.search(r'<meta property="og:title" content="([^"]+)"', page)
             or re.search(r"<title>([^<]+)</title>", page))
        name = html.unescape(t.group(1)).split(" - ")[0].strip() if t else cid.split("/")[-1]
    ch = {"id": cid, "name": name}
    notifications.add_new("Rumble", [i for i in _items(objs, ch) if i["kind"] != "live"])
    with LOCK:
        chs = load_channels()
        if not any(c["id"] == cid for c in chs):
            _save_channels(chs + [ch])
    return ch


def remove_channel(cid):
    _save_channels([c for c in load_channels() if c["id"] != cid])
    for i in notifications.load():
        if i.get("plugin") == "Rumble" and i.get("channel_id") == cid:
            notifications.remove(i["link"])


def fetch_rumble():
    channels = load_channels()
    if not channels:
        return []
    items, failed, err = [], 0, None
    for ch in channels:
        try:
            _, objs = _fetch_objs(ch["id"])
            items += _items(objs, ch)
        except Exception as e:
            failed, err = failed + 1, e
    if not items and failed:
        raise RuntimeError(f"all channels failed: {err!r}")
    items.sort(key=lambda i: i["ts"], reverse=True)
    return items[:100]