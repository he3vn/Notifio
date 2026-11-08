import sys
from pathlib import Path
 
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
 
RUMBLE = "Backend/rumble/feeds.py"
CARDS = "UI/components/cards.py"
 
OLD_VIEWS = '''def _views_of(o):
    v = _first(o, "views", "view_count", "viewCount", "watching_now", "viewers")
'''
NEW_VIEWS = '''def _views_of(o, live=False):  # live-aware patch
    keys = ("watching_now", "viewers") if live else ("views", "view_count", "viewCount")
    v = _first(o, *keys)
'''
 
EDITS = {
    RUMBLE: ("live-aware patch", [
        (OLD_VIEWS, NEW_VIEWS),
        ('"views": _views_of(o),', '"views": _views_of(o, live),'),
    ]),
    CARDS: ("watching patch", [
        ("    return f\"{text} {'watching' if item.get('plugin') == 'Twitch' else 'views'}\"\n",
         "    live = item.get(\"kind\") == \"live\" and item.get(\"plugin\") in (\"Twitch\", \"Rumble\")  # watching patch\n"
         "    return f\"{text} {'watching' if live else 'views'}\"\n"),
    ]),
}

def main():
    results,errors={}, []
    for rel,(mark,edits) in EDITS.items():
        path= ROOT/rel
        if not path.is_file():
            errors.append(f"{rel}: file not found")
            continue
        text=path.read_text(encoding="utf-8")
        if mark in text:
            print(f"skip   {rel} (already patched)")
            continue
        if rel ==RUMBLE and "thumbnails patch" not in text:
            errors.append(f"{rel}: run apply_thumbnails.py first")
            continue
        for old,new in edits:
            n=text.count(old)
            if n !=1:
                errors.append(f"{rel}: expected 1 match, found {n} for: {old[:70]!r}")
            text=text.replace(old,new)
        try:
            compile(text,rel,"exec")
        except SyntaxError as e:
            errors.append(f"{rel}: result would not compile ({e})")
        results[rel]= text

    if errors:
        print("Nothing was changed. Problems:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    for rel,text in results.items():
        path= ROOT/rel
        path.with_name(path.name + ".bak3").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        print(f"patched {rel}")
    print("Done. Restart Notifio.")

if __name__ == "__main__":
    main()