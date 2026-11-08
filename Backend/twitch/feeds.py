import json, re, threading, time, urllib.request
import notifications
from storage import get_data_dir, read_json, write_json
from dexerto.feeds import _ssl_context, _timestamp

GQL_URL = "https://gql.twitch.tv/gql"
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # Twitch web client's public ID
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
FILE = get_data_dir() / "twitch_channels.json"
BATCH = 30
LOGIN_RE = re.compile(r"[a-z0-9_]{3,25}")
LOCK = threading.RLock()


def load_channels():
    with LOCK:
        data = read_json(FILE, [])
        return data if isinstance(data, list) else []


def _save_channels(chs):
    with LOCK:
        write_json(FILE, chs)


def _users(logins):
    q = ('query { users(logins: %s) { login displayName '
         'stream { id title createdAt viewersCount game { name } } } }' % json.dumps(logins))
    req = urllib.request.Request(
        GQL_URL,
        data=json.dumps({"query": q}).encode(),
        headers={"Client-ID": CLIENT_ID, "Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=8, context=_ssl_context()) as r:
        payload = json.loads(r.read())
    if payload.get("errors") or not payload.get("data"):
        raise RuntimeError(f"twitch gql error: {payload.get('errors')!r}")
    return [u for u in payload["data"].get("users") or [] if u]



VODS_PER_CHANNEL = 5


def _vods(logins):
    """{login: [video nodes]}. Never raises: VODs are optional, live detection must not break."""
    q = ('query { users(logins: %s) { login videos(first: %d, type: ARCHIVE, sort: TIME) { edges { node { '
         'id title createdAt viewCount game { name } previewThumbnailURL(width: 640, height: 360) '
         '} } } } }' % (json.dumps(logins), VODS_PER_CHANNEL))
    try:
        req = urllib.request.Request(
            GQL_URL,
            data=json.dumps({"query": q}).encode(),
            headers={"Client-ID": CLIENT_ID, "Content-Type": "application/json", "User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=8, context=_ssl_context()) as r:
            payload = json.loads(r.read())
    except Exception:
        return {}
    out = {}
    for u in ((payload.get("data") or {}).get("users")) or []:
        if not u:
            continue
        edges = (u.get("videos") or {}).get("edges") or []
        out[u["login"]] = [e["node"] for e in edges if e and e.get("node")]
    return out


def _vod_items(u, vods, names, live_ts):
    login = u["login"]
    out = []
    for v in vods:
        ts = _timestamp(v.get("createdAt")) or time.time()
        if live_ts and abs(ts - live_ts) < 180:
            continue  # this is the recording of the stream that is live right now
        title = (v.get("title") or "").strip() or "Past broadcast"
        game = (v.get("game") or {}).get("name")
        out.append({
            "title": f"{title} ({game})" if game else title,
            "link": f"https://www.twitch.tv/videos/{v['id']}",
            "ts": ts,
            "source": u.get("displayName") or names.get(login, login),
            "channel_id": login,
            "kind": "video",
            "thumb": v.get("previewThumbnailURL") or None,
            "views": v.get("viewCount"),
        })
    return out


def parse_login(text):
    t = text.strip()
    m = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", t)
    login = (m.group(1) if m else t.lstrip("@/ ")).lower()
    if not LOGIN_RE.fullmatch(login):
        raise ValueError("enter a channel name or twitch.tv URL")
    return login


def add_channel(text):
    login = parse_login(text)
    if any(c["id"] == login for c in load_channels()):
        raise ValueError("already added")
    users = _users([login])
    if not users:
        raise ValueError("no channel with that name")
    ch = {"id": users[0]["login"], "name": users[0]["displayName"] or login}
    with LOCK:
        chs = load_channels()
        if not any(c["id"] == ch["id"] for c in chs):
            _save_channels(chs + [ch])
    return ch


def remove_channel(login):
    _save_channels([c for c in load_channels() if c["id"] != login])
    for i in notifications.load():
        if i.get("plugin") == "Twitch" and i.get("channel_id") == login:
            notifications.remove(i["link"])


def fetch_twitch():
    channels = load_channels()
    if not channels:
        return []
    names = {c["id"]: c["name"] for c in channels}
    items = []
    for i in range(0, len(channels), BATCH):
        batch = _users([c["id"] for c in channels[i:i + BATCH]])
        vods = _vods([u["login"] for u in batch])
        for u in batch:
            s = u.get("stream")
            live_ts = (_timestamp(s.get("createdAt")) if s else 0)
            items += _vod_items(u, vods.get(u["login"], []), names, live_ts)
            if not s:
                continue
            login = u["login"]
            game = (s.get("game") or {}).get("name")
            title = (s.get("title") or "").strip() or "Live now"
            items.append({
                "title": f"{title} ({game})" if game else title,
                "link": f"https://www.twitch.tv/{login}?stream={s['id']}",
                "ts": _timestamp(s.get("createdAt")) or time.time(),
                "source": u.get("displayName") or names.get(login, login),
                "channel_id": login,
                "kind": "live",
                "thumb": f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{login}-640x360.jpg?t={int(time.time() // 300)}",  # thumbnails patch
                "views": s.get("viewersCount"),
            })
    items.sort(key=lambda i: i["ts"], reverse=True)
    return items