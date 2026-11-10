import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import notifications
from dexerto.feeds import _timestamp
from net import FLAKY, UA, get_text, gunzip, http_get, run_parallel, ssl_context
from storage import get_data_dir, read_json, write_json

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"

FILE = get_data_dir() / "youtube_channels.json"
PREFS_FILE = get_data_dir() / "youtube_prefs.json"
KINDS_FILE = get_data_dir() / "youtube_kinds.json"  # video id -> kind, forever
VALID_TYPES = ["video", "short", "live"]
DEFAULT_TYPES = ["video", "short", "live"]
CLASSIFY_LIMIT = 30
RECHECK_EVERY = 60
FEED_WORKERS = 4       # channels fetched at once
CLASSIFY_WORKERS = 8   # new videos classified at once (global cap below)

# YouTube's feed endpoint throws random 404s at anonymous pollers - it is
# not the channel being gone, just flaky edge servers. Retry, it works.
FEED_RETRY = FLAKY | {404}

LOCK = threading.RLock()
_kinds_lock = threading.RLock()
_kinds = None                # lazy {videoId: kind}
_feed_cache = {}            # cid -> [etag, xml bytes] (stale fallback too)
_last_recheck = 0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_no_redirect_opener = None


def _redirect_opener():
    global _no_redirect_opener
    if _no_redirect_opener is None:
        _no_redirect_opener = urllib.request.build_opener(
            _NoRedirect, urllib.request.HTTPSHandler(context=ssl_context()))
    return _no_redirect_opener


def load_prefs():
    data = read_json(PREFS_FILE, None)
    if isinstance(data, list): return [t for t in data if t in VALID_TYPES]
    return list(DEFAULT_TYPES)


def save_prefs(types):
    write_json(PREFS_FILE, [t for t in VALID_TYPES if t in types])


def load_channels():
    with LOCK:
        data = read_json(FILE, [])
        return data if isinstance(data, list) else []


def _save_channels(chs):
    with LOCK:
        write_json(FILE, chs)


def resolve_channel_id(text):
    text = text.strip()
    m = re.search(r"(UC[\w-]{22})", text)
    if m and (text.startswith("UC") or "channel/" in text):
        return m.group(1)
    m = re.search(r"@([\w.\-]+)", text)
    handle = m.group(1) if m else text.lstrip("@/ ")
    if not re.fullmatch(r"[\w.\-]+", handle):
        raise ValueError("enter a @handle or channel URL")
    try:
        page = get_text(f"https://www.youtube.com/@{handle}", limit=2_000_000)
    except urllib.error.HTTPError as e:
        raise ValueError("no channel with that handle" if e.code == 404 else f"HTTP {e.code}")
    m = (re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', page)
         or re.search(r'"externalId":"(UC[\w-]{22})"', page)
         or re.search(r'"channelId":"(UC[\w-]{22})"', page))
    if not m:
        raise ValueError("couldn't find that channel")
    return m.group(1)


def add_channel(text):
    cid = resolve_channel_id(text)
    if any(c["id"] == cid for c in load_channels()):
        raise ValueError("already added")
    root = _feed_root(cid)
    ch = {"id": cid, "name": (root.findtext(ATOM + "title") or cid).strip()}
    items = _parse(root, ch, known=notifications.known_links("Youtube"))
    notifications.add_new("Youtube", items)
    with LOCK:
        chs = load_channels()
        if not any(c["id"] == cid for c in chs):
            _save_channels(chs + [ch])
    if "live" in load_prefs():
        for it in items:
            if it.get("kind") == "live":
                import notifier
                notifier.send(f'{ch["name"]} is LIVE now', it["title"], it["link"])
                break
    return ch


def remove_channel(cid):
    _save_channels([c for c in load_channels() if c["id"] != cid])
    for i in notifications.load():
        if i.get("plugin") == "Youtube" and i.get("channel_id") == cid:
            notifications.remove(i["link"])


# --- classification -----------------------------------------------------
#
# yt-dlp style: YouTube's internal API (InnerTube) answers in a few KB of
# JSON what used to cost a 1.4 MB watch-page scrape. Even better, the
# channel feed already labels shorts (their <link> points at /shorts/),
# so most videos are classified with zero extra requests:
#   * feed <link> says /shorts/            -> short (free)
#   * otherwise one POST /youtubei/v1/player (WEB client, no key):
#     microformat says live now / premiere / plain video
#   * last resort: the classic watch-page scrape
PLAYER_URL = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
PLAYER_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.youtube.com",
    "X-YouTube-Client-Name": "1",
    "X-YouTube-Client-Version": "2.20260708.00.00",
    "Referer": "https://www.youtube.com",
}
PLAYER_CTX = {"context": {"client": {"clientName": "WEB",
                                     "clientVersion": "2.20260708.00.00",
                                     "hl": "en", "gl": "US"}}}


def _read_page(resp, limit=3_000_000):
    return gunzip(resp.read(limit)).decode("utf-8", "ignore")


def _watch_page(vid):
    try:
        return get_text(f"https://www.youtube.com/watch?v={vid}",
                        timeout=10, limit=3_000_000)
    except Exception:
        return None


def _state_from_page(page):
    if '"isLive":true' in page:
        return "live"
    if '"isUpcoming":true' in page:
        return "upcoming"
    return None


def _innertube_player(vid):
    body = json.dumps({**PLAYER_CTX, "videoId": vid}).encode()
    req = urllib.request.Request(PLAYER_URL, data=body, headers=PLAYER_HEADERS)
    with urllib.request.urlopen(req, timeout=8, context=ssl_context()) as r:
        raw = gunzip(r.read(200_000))
    return json.loads(raw)


def _is_short(vid):
    """303 away from /shorts/ = normal video; staying (200) = a Short."""
    req = urllib.request.Request(f"https://www.youtube.com/shorts/{vid}",
                                  headers={"User-Agent": UA})
    try:
        with _redirect_opener().open(req, timeout=8) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307):
            return False
        raise


def _state_from_player(d, now=None):
    """live / upcoming / video from the player response, None if unsure."""
    now = now or time.time()
    vd = d.get("videoDetails") or {}
    mf = (d.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    lbd = mf.get("liveBroadcastDetails") or {}
    if lbd.get("isLiveNow") is True:
        return "live"
    start = _timestamp(lbd.get("startTimestamp")) if lbd.get("startTimestamp") else 0
    if lbd and start and start > now and not lbd.get("endTimestamp"):
        return "upcoming"           # scheduled premiere that hasn't started
    if vd.get("isLiveContent"):
        # stream-type content, but not live and not scheduled: it ended.
        # if the API left us no timestamps at all, stay unsure.
        if start or lbd.get("endTimestamp"):
            return "video"
        return None
    return "video"


def _classify_one(vid):
    """Full classification from a bare video id (redirect check + player)."""
    try:
        if _is_short(vid):
            return "short"
    except Exception:
        pass
    return _state_one(vid)


def _state_one(vid):
    """live / upcoming / video for a video already known not to be a Short."""
    try:
        state = _state_from_player(_innertube_player(vid))
        if state:
            return state
    except Exception:
        pass
    # fallback: the classic watch-page scrape, same as it ever was
    page = _watch_page(vid)
    return (_state_from_page(page) or "video") if page else "video"


def classify(vid):
    """Single video, without the cache (kept for manual/debug use)."""
    return _classify_one(vid)


def _load_kinds():
    global _kinds
    with _kinds_lock:
        if _kinds is None:
            d = read_json(KINDS_FILE, {})
            _kinds = d if isinstance(d, dict) else {}
        return _kinds


def _remember_kinds(fresh):
    """Persist videoId -> kind so every video is classified once, ever."""
    if not fresh:
        return
    with _kinds_lock:
        kinds = _load_kinds()
        if all(kinds.get(v) == k for v, k in fresh.items()):
            return
        kinds.update(fresh)
        try:
            write_json(KINDS_FILE, kinds)
        except Exception:
            pass


def _feed_root(cid):
    """Channel feed, or the last good copy if YouTube is being flaky."""
    headers = {}
    cached = _feed_cache.get(cid)
    if cached and cached[0]:
        headers["If-None-Match"] = cached[0]
    try:
        _, hdrs, body = http_get(
            f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}",
            headers=headers, timeout=8, tries=6, backoff=0.08, retry=FEED_RETRY)
        _feed_cache[cid] = [hdrs.get("ETag"), body]
    except Exception:
        # 304 means "unchanged"; anything else means flaky edge servers or
        # a dead network - if we ever got this channel, serve it stale.
        if not cached:
            raise
        body = cached[1]
    return ET.fromstring(body)


def _views(en):
    st = en.find(f"{MEDIA}group/{MEDIA}community/{MEDIA}statistics")
    try:
        return int(st.get("views")) if st is not None else None
    except (TypeError, ValueError):
        return None


def _parse(root, ch, known):
    entries = []
    for en in root.iter(ATOM + "entry"):
        vid = en.findtext(YT + "videoId")
        if not vid:
            continue
        link_el = en.find(ATOM + "link")
        href = link_el.get("href", "") if link_el is not None else ""
        # the feed links shorts at /shorts/{vid} - free classification.
        # the stored link stays watch?v= so old entries keep matching.
        kind = "short" if "/shorts/" in href else None
        entries.append((en, vid, f"https://www.youtube.com/watch?v={vid}", kind))

    kinds = _load_kinds()
    feed_shorts = {vid: "short" for _, vid, _, kind in entries if kind == "short"}
    if feed_shorts:
        _remember_kinds(feed_shorts)        # free classifications, keep them
    todo = [vid for _, vid, link, kind in entries
            if kind is None and link not in known and vid not in kinds][:CLASSIFY_LIMIT]
    if todo:
        fresh = {}
        for vid, kind, err in run_parallel(_state_one, todo, CLASSIFY_WORKERS):
            if err is None and kind:
                fresh[vid] = kind
        _remember_kinds(fresh)             # also updates `kinds` in place

    items = []
    for en, vid, link, feed_kind in entries:
        items.append({
            "title": (en.findtext(ATOM + "title") or "").strip(),
            "link": link,
            "ts": _timestamp(en.findtext(ATOM + "published")),
            "source": ch["name"],
            "channel_id": ch["id"],
            "kind": feed_kind or kinds.get(vid) or "video",
            "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "views": _views(en),
        })
    return items


def fetch_youtube():
    channels = load_channels()
    if not channels:
        return []
    known = notifications.known_links("Youtube")

    def work(ch):
        return _parse(_feed_root(ch["id"]), ch, known)

    items, failures = [], []
    for ch, parsed, err in run_parallel(work, channels, FEED_WORKERS):
        if err is not None:
            failures.append((ch.get("name") or ch.get("id"), err))
            continue
        items += parsed
    for name, err in failures:
        print(f"youtube: {name}: {err!r}", file=sys.stderr)
    if failures and not items:
        name, err = failures[0]
        raise RuntimeError(f"all {len(failures)} channels failed ({name}): {err!r}")
    items.sort(key=lambda i: i["ts"], reverse=True)
    _recheck_lives()
    return items[:100]


def _live_state(link):
    """live / upcoming / video for a stream video, None if the check failed."""
    try:
        d = _innertube_player(link.split("v=")[-1])
        return _state_from_player(d)
    except Exception:
        page = _watch_page(link.split("v=")[-1])
        if page is None:
            return None            # couldn't fetch, leave it for next round
        return _state_from_page(page) or "video"


def _recheck_lives():
    global _last_recheck
    if time.time() - _last_recheck < RECHECK_EVERY:
        return
    _last_recheck = time.time()
    candidates = []
    for item in notifications.load():
        if item.get("plugin") != "Youtube":
            continue
        # upcoming streams become live, and live streams need one more look
        # after they end so they can be downloaded like a normal video.
        if item.get("kind") not in ("upcoming", "live", None):
            continue
        link = item.get("link", "")
        if "v=" not in link:
            continue
        candidates.append(link)
        if len(candidates) >= 5:
            break
    if not candidates:
        return

    updates = {}
    for link, state, err in run_parallel(_live_state, candidates, len(candidates)):
        if err is not None or state is None:
            continue
        updates[link] = state
    if not updates:
        return
    _remember_kinds({l.split("v=")[-1]: k for l, k in updates.items()})

    newly_live = []
    with notifications.LOCK:
        history = notifications.load()
        changed = False
        for item in history:
            new_kind = updates.get(item.get("link"))
            if new_kind and item.get("kind") != new_kind:
                if new_kind == "live":
                    newly_live.append(item)
                item["kind"] = new_kind
                changed = True
        if changed:
            notifications.save(history)

    if newly_live and "live" in load_prefs():
        import notifier
        for item in newly_live:
            notifier.send(f'{item["source"]} is LIVE now', item["title"], item["link"])


def force_recheck():
    global _last_recheck
    _last_recheck = 0
