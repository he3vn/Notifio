# I made some research on yt dlp from their docs but most of this will be done by ai I will disclose it
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

DOWNLOADER = r'''import importlib.util
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
import app_settings

WINDOWS = sys.platform.startswith("win")
QUALITIES = app_settings.CHOICES["download_quality"]
SOURCES = ("Youtube", "Twitch", "Rumble")
ACTIVE = ("queued", "downloading", "processing")


for _d in ("/opt/homebrew/bin", "/usr/local/bin"):
    _parts = os.environ.get("PATH", "").split(os.pathsep)
    if os.path.isdir(_d) and _d not in _parts:
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + _d

JOBS = {}
_WATCH = {}
_LOCK = threading.RLock()
_SEM = threading.Semaphore(2)


def folder():
    p = Path.home() / "Downloads" / "Notifio"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ffmpeg_path():
    root = Path(os.environ.get("NOTIFIO_ROOT", "."))
    bundled = root / "Assets" / ("ffmpeg.exe" if WINDOWS else "ffmpeg")
    if bundled.is_file():
        return str(bundled)
    return shutil.which("ffmpeg")


def status_text():
    if importlib.util.find_spec("yt_dlp") is None:
        return 'yt-dlp is not installed. Run: pip install -U "yt-dlp[default]"'
    try:
        from importlib.metadata import version
        ver = version("yt-dlp")
    except Exception:
        ver = "installed"
    bits = [f"yt-dlp {ver}"]
    if not ffmpeg_path():
        bits.append("ffmpeg missing: no merging, lower quality")
    if not shutil.which("deno"):
        bits.append("deno missing: YouTube may fail")
    return " | ".join(bits)


def can_download(item):
    if item.get("plugin") not in SOURCES or not item.get("link"):
        return False
    return item.get("kind") in (None, "video", "short")


def job(link):
    with _LOCK:
        j = JOBS.get(link)
        return dict(j) if j else None


def watch(link, fn):
    _WATCH[link] = fn


def clear_finished():
    with _LOCK:
        for k in [k for k, j in JOBS.items() if j["state"] not in ACTIVE]:
            JOBS.pop(k, None)


def _set(link, **kw):
    with _LOCK:
        j = JOBS.setdefault(link, {"state": "queued", "pct": 0.0, "speed": 0, "eta": None,
                                   "error": "", "file": "", "quality": ""})
        j.update(kw)
    fn = _WATCH.get(link)
    if fn:
        try:
            fn()
        except Exception:
            pass


def describe(j):
    """Short status text for a card."""
    st = j["state"]
    if st == "queued":
        return "Starting..."
    if st == "processing":
        return "Processing..."
    if st == "done":
        return "Saved"
    if st == "error":
        return j.get("error") or "Failed"
    bits = [f"{int(j['pct'] * 100)}%"]
    if j.get("speed"):
        bits.append(f"{j['speed'] / 1e6:.1f} MB/s")
    if j.get("eta") is not None:
        e = int(j["eta"])
        bits.append(f"{e // 60}:{e % 60:02d} left")
    return "  ".join(bits)

# I will let ai handle the rest for the formats might be a lot of converting
def format_for(q, has_ffmpeg):
    if q == "Audio only":
        return "ba/b" if has_ffmpeg else "ba[ext=m4a]/ba/b"
    if q == "Best":
        return "bv*+ba/b" if has_ffmpeg else "b"
    h = int(q[:-1])
    if has_ffmpeg:
        return f"bv*[height<={h}]+ba/b[height<={h}]/w"
    return f"b[height<={h}]/b"


def _clean(e):
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e))
    msg = msg.replace("ERROR: ", "").strip().splitlines()[-1] if msg.strip() else "Failed"
    return msg[:140]


def start(item, quality=None):
    """Queue a download. quality=None uses the default from settings."""
    link = item.get("link")
    if not link:
        return False
    q = quality if quality in QUALITIES else app_settings.get("download_quality")
    with _LOCK:
        j = JOBS.get(link)
        if j and j["state"] in ACTIVE:
            return False
        JOBS[link] = {"state": "queued", "pct": 0.0, "speed": 0, "eta": None,
                      "error": "", "file": "", "quality": q}
    _set(link, state="queued")
    threading.Thread(target=_run, args=(link, q), daemon=True).start()
    return True


def _final_path(info):
    try:
        rd = (info or {}).get("requested_downloads") or []
        if rd and rd[0].get("filepath"):
            return rd[0]["filepath"]
    except Exception:
        pass
    return ""


def _run(link, quality):
    with _SEM:
        _set(link, state="downloading", pct=0.0)
        try:
            import yt_dlp
        except Exception:
            _set(link, state="error", error="yt-dlp not installed (pip install -U yt-dlp)")
            return
        ff = ffmpeg_path()
        stage = {"n": 0, "last": 0.0}

        def hook(d):
            try:
                st = d.get("status")
                n = len((d.get("info_dict") or {}).get("requested_formats") or []) or 1
                if st == "finished":
                    stage["n"] += 1
                    return
                if st != "downloading":
                    return
                now = time.monotonic()
                if now - stage["last"] < 0.25:
                    return
                stage["last"] = now
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                if total:
                    p = done / total
                elif d.get("fragment_count"):
                    p = (d.get("fragment_index") or 0) / d["fragment_count"]
                else:
                    p = 0.0
                overall = min(0.99, (stage["n"] + min(p, 1.0)) / n)
                _set(link, state="downloading", pct=overall,
                     speed=d.get("speed") or 0, eta=d.get("eta"))
            except Exception:
                pass

        def pp_hook(d):
            if d.get("status") == "started":
                _set(link, state="processing", pct=1.0)

        opts = {
            "format": format_for(quality, bool(ff)),
            "format_sort": ["res", "ext:mp4:m4a"],
            "outtmpl": str(folder() / "%(title).120B [%(id)s].%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 5,
            "concurrent_fragment_downloads": 4,
            "progress_hooks": [hook],
            "postprocessor_hooks": [pp_hook],
        }
        if ff:
            opts["ffmpeg_location"] = ff
            opts["merge_output_format"] = "mp4"
            if quality == "Audio only":
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                           "preferredcodec": "mp3", "preferredquality": "192"}]
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
            _set(link, state="done", pct=1.0, file=_final_path(info))
        except Exception as e:
            traceback.print_exc()
            _set(link, state="error", error=_clean(e))


def _open_path(args):
    try:
        subprocess.Popen(args)
    except Exception:
        traceback.print_exc()


def open_folder():
    p = str(folder())
    if sys.platform == "darwin":
        _open_path(["open", p])
    elif WINDOWS:
        _open_path(["explorer", p])


def reveal(link):
    j = job(link)
    path = (j or {}).get("file")
    if not path or not Path(path).exists():
        open_folder()
        return
    if sys.platform == "darwin":
        _open_path(["open", "-R", path])
    elif WINDOWS:
        _open_path(["explorer", f"/select,{path}"])
'''

NEW_FILES = {"Backend/downloader.py": DOWNLOADER}

CARDS_FUNC = r'''def _download_ui(item, on_download, on_choose):
    """Download icon + quality chevron (title row) and progress row. (None, None) if not downloadable."""
    link = item.get("link") or ""
    if not (on_download and link and downloader.can_download(item)):
        return None, None
    ACC, OK, BAD = "#5e6ad2", "#3fb950", "#ef6b6b"
    btn = ft.IconButton(icon=ft.Icons.DOWNLOAD_ROUNDED, icon_size=18, icon_color=S,
                        width=32, height=32, tooltip="Download")
    more = ft.IconButton(icon=ft.Icons.ARROW_DROP_DOWN, icon_size=18, icon_color=S,
                         width=22, height=32, tooltip="Choose quality",
                         on_click=lambda e, it=item: on_choose(it) if on_choose else None)
    bar = ft.ProgressBar(value=0, bar_height=4, color=ACC, bgcolor="#2a2c31",
                         border_radius=2, expand=True)
    info = ft.Text("", size=11, color=S, font_family="Inter-Medium")
    progress = ft.Container(
        visible=False, padding=ft.Padding(4, 0, 4, 4),
        content=ft.Row([bar, info], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def refresh():
        j = downloader.job(link)
        st = j["state"] if j else "idle"
        progress.visible = st != "idle"
        bar.visible = st in downloader.ACTIVE or st == "done"
        if st in downloader.ACTIVE:
            btn.icon, btn.icon_color, btn.tooltip = ft.Icons.DOWNLOAD_ROUNDED, ACC, "Downloading..."
            bar.value = None if st in ("queued", "processing") else j["pct"]
        elif st == "done":
            btn.icon, btn.icon_color, btn.tooltip = ft.Icons.CHECK_CIRCLE_ROUNDED, OK, "Show in folder"
            bar.value = 1
        elif st == "error":
            btn.icon, btn.icon_color, btn.tooltip = ft.Icons.ERROR_OUTLINE, BAD, "Failed. Click to retry"
        else:
            btn.icon, btn.icon_color, btn.tooltip = ft.Icons.DOWNLOAD_ROUNDED, S, "Download"
        info.value = downloader.describe(j) if j else ""
        info.color = BAD if st == "error" else S
        for c in (btn, progress):
            try:
                c.update()
            except Exception:
                pass

    def click(e):
        j = downloader.job(link)
        st = j["state"] if j else "idle"
        if st == "done":
            downloader.reveal(link)
        elif st not in downloader.ACTIVE:
            on_download(item)

    btn.on_click = click
    downloader.watch(link, refresh)
    refresh()
    return ft.Row([btn, more], spacing=0, tight=True), progress


def _card(item, on_delete, on_download=None, on_choose=None):'''

CARDS_BODY_OLD = '''            ft.Container(height=38, padding=ft.Padding(4, 0, 4, 0), content=ft.Text(
                item.get("title", ""), size=14, color=H, font_family="Inter-SemiBold",
                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)),
            ft.Container(padding=ft.Padding(4, 0, 4, 2), content=ft.Text(
                meta, size=12, color=S, font_family="Inter-Medium",
                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
        ]),
'''
CARDS_BODY_NEW = '''            ft.Container(height=38, padding=ft.Padding(4, 0, 4, 0), content=ft.Row(
                [ft.Text(item.get("title", ""), size=14, color=H, font_family="Inter-SemiBold",
                         max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True)]
                + ([dl_controls] if dl_controls else []),
                spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)),
            ft.Container(padding=ft.Padding(4, 0, 4, 2), content=ft.Text(
                meta, size=12, color=S, font_family="Inter-Medium",
                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
            *([progress] if progress else []),
        ]),
'''

HOME_METHODS = r'''# downloads patch
    def _build_downloads_box(self):
        cur = app_settings.get("download_quality")
        self.dl_status = ft.Text("", size=11, color=S)
        dd = ft.Dropdown(
            value=cur, width=240, dense=True, text_size=13,
            options=[ft.DropdownOption(key=q, text=q) for q in downloader.QUALITIES],
        )

        def changed(e):
            v = getattr(e.control, "value", None)
            if v in downloader.QUALITIES:
                app_settings.set_value("download_quality", v)

        for attr in ("on_select", "on_change"):  # name differs between flet versions
            try:
                setattr(dd, attr, changed)
            except Exception:
                pass
        self.dl_box = ft.Container(
            visible=False, right=16, top=BAR_H+24, width=300, padding=18,
            bgcolor="#000000", border_radius=18,
            border=ft.Border.all(1, "#23252a"),
            shadow=[ft.BoxShadow(blur_radius=24, color="#66000000", offset=ft.Offset(0, 8))],
            content=ft.Column(spacing=10, tight=True, controls=[
                ft.Text("Downloads", size=15, color=H, font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
                ft.Text("Default quality", size=12, color=S),
                dd,
                ft.Text(f"Saved to {downloader.folder()}", size=11, color=S),
                ft.Button("Open folder", on_click=lambda e: downloader.open_folder(), height=38, style=BTN),
                self.dl_status,
            ]),
        )

    def _toggle_downloads(self,e):
        self.settings_box.visible=False
        self.dl_box.visible=not self.dl_box.visible
        if self.dl_box.visible:
            self.dl_status.value=downloader.status_text()
        self._safe_update()

    def _download(self,item,quality=None):
        downloader.start(item,quality)

    def _choose_quality(self,item):
        cur=app_settings.get("download_quality")

        def pick(q):
            self._close_dialog(dlg)
            self._download(item,q)

        def chip(q):
            on=q==cur
            return ft.Container(
                padding=ft.Padding(14,10,14,10),border_radius=10,
                bgcolor="#1c1d20" if on else "#141516",
                border=ft.Border.all(1,"#5e6ad2" if on else "#23252a"),
                on_click=lambda e,q=q:pick(q),
                content=ft.Text(q+("  (default)" if on else ""),size=13,color=H,font_family="Inter-Medium"),
            )

        dlg=ft.AlertDialog(
            title=ft.Text("Download quality"),
            content=ft.Column([chip(q) for q in downloader.QUALITIES],tight=True,spacing=6,width=260),
            actions=[ft.TextButton("Cancel",on_click=lambda ev:self._close_dialog(dlg))],
        )
        self._open_dialog(dlg)

    def _cards(self,items,empty):  # thumbnails patch
'''

HOME_STACK_OLD = '''        self.content=ft.Stack(expand=True,controls=[self.wall,self.veil,ft.Container(left=0,right=0,top=0,bottom=0,content=ft.Column(expand=True,spacing=0,controls=[top_bar, panel])),self.settings_box])'''
HOME_STACK_NEW = '''        self._build_downloads_box()
        self.content=ft.Stack(expand=True,controls=[self.wall,self.veil,ft.Container(left=0,right=0,top=0,bottom=0,content=ft.Column(expand=True,spacing=0,controls=[top_bar, panel])),self.settings_box,self.dl_box])'''

EDITS = {
    "Backend/app_settings.py": ("download_quality", [
        ('    "close_to_tray": True,\n}',
         '    "close_to_tray": True,\n    "download_quality": "720p",\n}'),
        ('    "group_after": [1, 3, 5, 10],\n',
         '    "group_after": [1, 3, 5, 10],\n'
         '    "download_quality": ["Best", "1080p", "720p", "480p", "360p", "240p", "144p", "Audio only"],\n'),
    ]),
    "UI/components/cards.py": ("_download_ui", [
        ("import flet as ft\nfrom dexerto.feeds import ago, fmt_count\n",
         "import flet as ft\nimport downloader  # downloads patch\nfrom dexerto.feeds import ago, fmt_count\n"),
        ("def _card(item, on_delete):", CARDS_FUNC),
        ('    body = ft.Container(\n        url=item.get("link") or None,\n',
         '    dl_controls, progress = _download_ui(item, on_download, on_choose)\n'
         '    body = ft.Container(\n        url=item.get("link") or None,\n'),
        (CARDS_BODY_OLD, CARDS_BODY_NEW),
        ("def card_grid(items, on_delete):", "def card_grid(items, on_delete, on_download=None, on_choose=None):"),
        ("[_card(i, on_delete) for i in items]", "[_card(i, on_delete, on_download, on_choose) for i in items]"),
    ]),
    "UI/components/home_screen.py": ("_build_downloads_box", [
        ("import sound\n", "import sound\nimport downloader  # downloads patch\n"),
        (HOME_STACK_OLD, HOME_STACK_NEW),
        ('                    action(ft.Icons.ADD,"Add plugin",self._add_plugin),\n',
         '                    action(ft.Icons.ADD,"Add plugin",self._add_plugin),\n'
         '                    action(ft.Icons.DOWNLOAD_ROUNDED,"Downloads",self._toggle_downloads),\n'),
        ("    def _toggle_settings(self,e):\n        self.settings_box.visible=not self.settings_box.visible\n",
         "    def _toggle_settings(self,e):\n        self.dl_box.visible=False\n        self.settings_box.visible=not self.settings_box.visible\n"),
        ("    def _view_changed(self):\n        self.settings_box.visible=False\n",
         "    def _view_changed(self):\n        self.settings_box.visible=False\n        self.dl_box.visible=False\n"),
        ("    def _cards(self,items,empty):  # thumbnails patch\n", "    " + HOME_METHODS),
        ("        return [card_grid(items,self._delete)]",
         "        return [card_grid(items,self._delete,self._download,self._choose_quality)]"),
    ]),
    "build.py": ("yt_dlp", [
        ('    "webbrowser",\n]',
         '    "webbrowser",\n    "yt_dlp",\n    "yt_dlp_ejs",\n]'),
    ]),
    "requirements.txt": ("yt-dlp", [
        ("curl_cffi\n", 'curl_cffi\nyt-dlp[default]\n'),
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
    print('Done. Run: pip install -U "yt-dlp[default]"  and  brew install ffmpeg deno  then restart Notifio.')


if __name__ == "__main__":
    main()