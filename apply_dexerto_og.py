import sys
from pathlib import Path
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
p = root / "Backend" / "dexerto" / "feeds.py"
s = p.read_text(encoding="utf-8")
if "_og_image" in s:
    sys.exit("already applied")
if "thumbnails patch" not in s:
    sys.exit("run apply_thumbnails.py first")
FUNC = '''_OG={}
def _og_image(url):
    if url in _OG:
        return _OG[url]
    img=None
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (Macintosh) Notifio/1.0"})
        with urllib.request.urlopen(req,timeout=8,context=_ssl_context()) as r:
            page=r.read(300_000).decode("utf-8","ignore")
        m=(re.search(r'<meta[^>]+property=["\\']og:image["\\'][^>]+content=["\\']([^"\\']+)',page)
           or re.search(r'<meta[^>]+content=["\\']([^"\\']+)["\\'][^>]+property=["\\']og:image["\\']',page))
        img=m.group(1) if m else None
    except Exception:
        pass
    _OG[url]=img
    return img

def fetch_feed('''
HOOK = '''    for i in items[:limit]:
        if not i.get("thumb") and i["link"]:
            i["thumb"]=_og_image(i["link"])
    items=items[:limit]
'''
assert s.count("def fetch_feed(") == 1 and s.count("    items=items[:limit]\n") == 1
s = s.replace("def fetch_feed(", FUNC, 1).replace("    items=items[:limit]\n", HOOK, 1)
compile(s, str(p), "exec")
p.with_name("feeds.py.bak2").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
p.write_text(s, encoding="utf-8")
print("patched Backend/dexerto/feeds.py. Restart Notifio.")