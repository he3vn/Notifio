import ssl, time, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

ATOM = "{http://www.w3.org/2005/Atom}"

# plugin name -> list of (source label, feed url)
FEEDS = {
    "News": [
        ("Dexerto", "https://www.dexerto.com/feed/"),
    ],
}


def _ssl_context():
    # python.org builds on macOS often lack root certs; certifi fixes that
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _timestamp(text):
    if not text:
        return 0
    try:
        return parsedate_to_datetime(text).timestamp()  # RSS dates
    except Exception:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()  # Atom dates
    except Exception:
        return 0


def ago(ts):
    if not ts:
        return ""
    s = max(0, time.time() - ts)
    for unit, secs in (("d", 86400), ("h", 3600), ("m", 60)):
        if s >= secs:
            return f"{int(s // secs)}{unit} ago"
    return "just now"


def fetch_feed(source, url, limit=15):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh) Notifio/1.0"},
    )
    with urllib.request.urlopen(req, timeout=8, context=_ssl_context()) as r:
        root = ET.fromstring(r.read())

    items = []
    for it in root.iter("item"):  # RSS format
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "ts": _timestamp(it.findtext("pubDate")),
            "source": source,
        })
    for en in root.iter(ATOM + "entry"):  # Atom format
        link = en.find(ATOM + "link")
        items.append({
            "title": (en.findtext(ATOM + "title") or "").strip(),
            "link": link.get("href", "") if link is not None else "",
            "ts": _timestamp(en.findtext(ATOM + "published") or en.findtext(ATOM + "updated")),
            "source": source,
        })
    return items[:limit]


def fetch_all(feeds):
    items, failed, last_error = [], 0, None
    for source, url in feeds:
        try:
            items += fetch_feed(source, url)
        except Exception as e:
            failed += 1
            last_error = e
    if not items and failed:
        raise RuntimeError(f"all feeds failed: {last_error!r}")
    items.sort(key=lambda i: i["ts"], reverse=True)
    return items[:40]