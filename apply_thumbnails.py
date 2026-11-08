#Vibecoded the thumbnails part
#!/usr/bin/env python3
"""Adds thumbnails + view counts to Notifio.

Run from the project root:   python3 apply_thumbnails.py
(also copy cards.py into UI/components/ first)

Every edit is checked before anything is written. If an anchor is not found the script
stops and changes nothing. Originals are saved next to each file as *.bak.
"""
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
MARK = "thumbnails patch"


def lit(old, new, count=1):
    return ("lit", old, new, count)


def rx(pattern, repl, count=1):
    return ("rx", pattern, repl, count)


# ---------------------------------------------------------------- dexerto
DEXERTO_HELPERS = r'''# --- thumbnails patch ---
MEDIA = "{http://search.yahoo.com/mrss/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def fmt_count(n):
    """1234 -> 1.2K, 3400000 -> 3.4M"""
    try:
        n = int(n)
    except Exception:
        return ""
    for div, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= div:
            v = n / div
            if v >= 100:
                return f"{int(v)}{suffix}"
            return f"{v:.1f}".rstrip("0").rstrip(".") + suffix
    return str(n)


def _image(it):
    """Best image for an RSS <item> / Atom <entry>: media tags, enclosure, then first <img> in the body."""
    for tag in (MEDIA + "thumbnail", MEDIA + "content"):
        for el in it.iter(tag):
            url = el.get("url") or ""
            if url and (tag.endswith("thumbnail") or el.get("medium") == "image"
                        or (el.get("type") or "").startswith("image")
                        or url.lower().split("?")[0].endswith(IMG_EXT)):
                return url
    enc = it.find("enclosure")
    if enc is not None and (enc.get("type") or "").startswith("image") and enc.get("url"):
        return enc.get("url")
    body = it.findtext(CONTENT + "encoded") or it.findtext("description") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', body)
    return m.group(1) if m else None
# --- end thumbnails patch ---


_CACHE= {}
'''

# ---------------------------------------------------------------- youtube
YT_VIEWS = r'''# thumbnails patch: view count from <media:statistics views="..."/>
def _views(en):
    st = en.find(f"{MEDIA}group/{MEDIA}community/{MEDIA}statistics")
    try:
        return int(st.get("views")) if st is not None else None
    except (TypeError, ValueError):
        return None


def _parse(root,ch,known):'''

# ---------------------------------------------------------------- rumble
RUMBLE_HELPERS = r'''# thumbnails patch: Rumble's embedded JSON key names are not documented, so try several
def _first(o, *keys):
    for k in keys:
        v = o.get(k)
        if v:
            return v
    return None


def _thumb_of(o):
    v = _first(o, "thumb", "thumbnail", "thumbnail_url", "thumbnailUrl", "image", "poster")
    if isinstance(v, list) and v:
        v = v[0]
    if isinstance(v, dict):
        v = _first(v, "url", "src", "large", "medium", "small")
    if not isinstance(v, str):
        # fallback: any top-level string value that looks like an image URL
        v = next((x for x in o.values() if isinstance(x, str)
                  and x.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp"))), None)
    if isinstance(v, str):
        return "https:" + v if v.startswith("//") else v
    return None


def _views_of(o):
    v = _first(o, "views", "view_count", "viewCount", "watching_now", "viewers")
    if v is None:
        return None
    try:
        return int(str(v).replace(",", "").strip())
    except ValueError:
        return None


def _items(objs, channel):'''

# ---------------------------------------------------------------- notifications
NOTIF_REFRESH = '''        # thumbnails patch: keep views/thumb of already-stored items up to date
        stats_changed = False
        fresh_by_link = {i["link"]: i for i in fetched if i.get("link")}
        for h in history:
            f = fresh_by_link.get(h.get("link"))
            if not f:
                continue
            for k in ("views", "thumb"):
                v = f.get(k)
                if v is not None and v != h.get(k):
                    h[k] = v
                    stats_changed = True
        if first:
            seen[plugin] = []
        if new or restored or stats_changed:
'''

# ---------------------------------------------------------------- home screen
CARDS_METHOD = '''    def _cards(self,items,empty):  # thumbnails patch
        if not items:
            return [ft.Text(empty,size=13,color=S)] if empty else []
        return [card_grid(items,self._delete)]

    def _delete(self,item):
'''

EDITS = {
    "Backend/dexerto/feeds.py": [
        lit("import ssl, time, urllib.request,urllib.error",
            "import re, ssl, time, urllib.request,urllib.error"),
        lit("_CACHE= {}\n", DEXERTO_HELPERS),
        lit('"ts":_timestamp(it.findtext("pubDate")) or now,',
            '"ts":_timestamp(it.findtext("pubDate")) or now,\n            "thumb":_image(it),'),
        lit('"ts":_timestamp(en.findtext(ATOM+"published")or en.findtext(ATOM+"updated")) or now,',
            '"ts":_timestamp(en.findtext(ATOM+"published")or en.findtext(ATOM+"updated")) or now,\n'
            '            "thumb":_image(en),'),
    ],
    "Backend/youtube/feeds.py": [
        lit('YT="{http://www.youtube.com/xml/schemas/2015}"\n',
            'YT="{http://www.youtube.com/xml/schemas/2015}"\nMEDIA="{http://search.yahoo.com/mrss/}"\n'),
        lit("def _parse(root,ch,known):", YT_VIEWS),
        lit('"kind":kind,',
            '"kind":kind,\n'
            '            "thumb":f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",  # thumbnails patch\n'
            '            "views":_views(en),'),
    ],
    "Backend/twitch/feeds.py": [
        lit("stream { id title createdAt game { name } } } }",
            "stream { id title createdAt viewersCount game { name } } } }"),
        lit('"kind": "live",',
            '"kind": "live",\n'
            '                "thumb": f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{login}-640x360.jpg'
            '?t={int(time.time() // 300)}",  # thumbnails patch\n'
            '                "views": s.get("viewersCount"),'),
    ],
    "Backend/rumble/feeds.py": [
        lit("def _items(objs, channel):", RUMBLE_HELPERS),
        lit('"kind": kind,',
            '"kind": kind,\n'
            '            "thumb": _thumb_of(o),  # thumbnails patch\n'
            '            "views": _views_of(o),'),
    ],
    "Backend/notifications.py": [
        rx(r"        if first:\n            seen\[plugin\] = \[\]\n        if new or restored:\n",
           lambda m: NOTIF_REFRESH),
    ],
    "UI/components/home_screen.py": [
        lit("from dexerto.feeds import FEEDS, ago\n",
            "from dexerto.feeds import FEEDS, ago\nfrom .cards import card_grid  # thumbnails patch\n"),
        lit("self.body.controls = [self._row(i) for i in items]",
            'self.body.controls = self._cards(items, "")'),
        rx(r'\*\(\[self\._row\(i\) for i in items\]\s*or \[ft\.Text\(("[^"]*"),\s*size=13,\s*color=S\)\]\),',
           lambda m: f"*self._cards(items, {m.group(1)}),", count=3),
        lit("    def _delete(self,item):\n", CARDS_METHOD),
    ],
}


def main():
    if not (ROOT / "UI" / "components" / "cards.py").is_file():
        sys.exit("Copy cards.py into UI/components/ first, then run this again from the project root.")

    results, errors = {}, []
    for rel, edits in EDITS.items():
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"{rel}: file not found")
            continue
        text = path.read_text(encoding="utf-8")
        if MARK in text:
            print(f"skip   {rel} (already patched)")
            continue
        for kind, a, b, want in edits:
            if kind == "lit":
                found = text.count(a)
                text = text.replace(a, b)
            else:
                text, found = re.subn(a, b, text)
            if found != want:
                errors.append(f"{rel}: expected {want} match(es), found {found} for: {a[:70]!r}")
        try:
            compile(text, rel, "exec")
        except SyntaxError as e:
            errors.append(f"{rel}: result would not compile ({e})")
        results[rel] = text

    if errors:
        print("Nothing was changed. Problems:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    for rel, text in results.items():
        path = ROOT / rel
        path.with_name(path.name + ".bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        print(f"patched {rel}")
    print("Done. Restart Notifio.")


if __name__ == "__main__":
    main()