
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

NEW_FILES = {}

TWITCH_HELPERS = r'''
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
'''

TWITCH_LOOP_OLD = '''        for u in _users([c["id"] for c in channels[i:i + BATCH]]):
            s = u.get("stream")
            if not s:
                continue
'''
TWITCH_LOOP_NEW = '''        batch = _users([c["id"] for c in channels[i:i + BATCH]])
        vods = _vods([u["login"] for u in batch])
        for u in batch:
            s = u.get("stream")
            live_ts = (_timestamp(s.get("createdAt")) if s else 0)
            items += _vod_items(u, vods.get(u["login"], []), names, live_ts)
            if not s:
                continue
'''

POLLER_FILTER_OLD = """            if i.get("plugin")=="Youtube" and kind and PREF_OF.get(kind,kind) not in wanted:
                continue
"""
POLLER_FILTER_NEW = """            if i.get("plugin")=="Youtube" and kind and PREF_OF.get(kind,kind) not in wanted:
                continue
            if i.get("plugin")=="Twitch" and kind=="video":  # VODs appear silently
                continue
"""

EDITS = {
    "Backend/twitch/feeds.py": ("_vods", [
        ("def parse_login(text):\n", TWITCH_HELPERS),
        (TWITCH_LOOP_OLD, TWITCH_LOOP_NEW),
    ]),
    "Backend/poller.py": ("VODs appear silently", [
        (POLLER_FILTER_OLD, POLLER_FILTER_NEW),
    ]),
}


def main():
    results, errors, created = {}, [], {}

    for rel, text in NEW_FILES.items():
        path = ROOT / rel
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            print(f"skip   {rel} (already exists)")
            continue
        try:
            compile(text, rel, "exec")
        except SyntaxError as e:
            errors.append(f"{rel}: would not compile ({e})")
        created[rel] = text

    for rel, (mark, edits) in EDITS.items():
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"{rel}: file not found")
            continue
        text = path.read_text(encoding="utf-8")
        if mark in text:
            print(f"skip   {rel} (already patched)")
            continue
        for old, new in edits:
            n = text.count(old)
            if n != 1:
                errors.append(f"{rel}: expected 1 match, found {n} for: {old[:70]!r}")
                continue
            text = text.replace(old, new)
        if rel.endswith(".py"):
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

    for rel, text in created.items():
        (ROOT / rel).write_text(text, encoding="utf-8")
        print(f"created {rel}")
    for rel, text in results.items():
        path = ROOT / rel
        path.with_name(path.name + ".bak4").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        print(f"patched {rel}")
    print('Done. Restart Notifio.')


if __name__ == "__main__":
    main()