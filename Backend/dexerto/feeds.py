import ssl, time, urllib.request,urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ATOM = "{http://www.w3.org/2005/Atom}"

FEEDS = {
    "News": [
        ("Dexerto", "https://www.dexerto.com/feed/"),
    ],
}


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _timestamp(text):
    if not text:
        return 0
    try:
        return parsedate_to_datetime(text).timestamp()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0


def clean_link(url):
    try:
        p = urlsplit(url)
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
        return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))
    except Exception:
        return url


def ago(ts):
    if not ts:
        return ""
    s = max(0, time.time() - ts)
    for unit, secs in (("d", 86400), ("h", 3600), ("m", 60)):
        if s >= secs:
            return f"{int(s // secs)}{unit} ago"
    return "just now"

_CACHE= {}
def fetch_feed(source, url, limit=15):
    headers={"User-Agent":"Mozilla/5.0 (Macintosh) Notifio/1.0"}
    c=_CACHE.get(url)
    if c:
        if c[0]:headers["If-None-Match"]=c[0]
        if c[1]:headers["If-Modified-Since"]=c[1]
    req=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=8,context=_ssl_context()) as r:
            body=r.read()
            etag=r.headers.get("Etag")
            lm=r.headers.get("Last-Modified")
    except urllib.error.HTTPError as e:
        if e.code== 304 and c:
            return c[2]
        raise
    root=ET.fromstring(body)

    now=time.time()
    items=[]
    for it in root.iter("item"):
        items.append({
            "title":(it.findtext("title")or "").strip(),
            "link": clean_link((it.findtext("link") or "").strip()),
            "ts":_timestamp(it.findtext("pubDate")) or now,
            "source":source,
        })
    for en in root.iter(ATOM + "entry"):
        link=en.find(ATOM+"link")
        items.append({
            "title":(en.findtext(ATOM+"title")or "").strip(),
            "link":clean_link(link.get("href",""))if link is not None else "",
            "ts":_timestamp(en.findtext(ATOM+"published")or en.findtext(ATOM+"updated")) or now,
            "source":source,
        })
    items=items[:limit]
    _CACHE[url]=(etag,lm,items)
    return items
    


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
