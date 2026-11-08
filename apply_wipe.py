import sys
from pathlib import Path
 
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
 
APP_RESET = r'''import os
import traceback
from pathlib import Path
import app_settings
import control
import notifications
from storage import get_data_dir
 
DATA_FILES = (
    "notifications.json", "seen.json", "user.json", "user_setup.json",
    "selected_plugins.json", "youtube_channels.json", "youtube_prefs.json",
    "twitch_channels.json", "rumble_channels.json", "settings.json",
)
DEV_FILES = ("user_setup.json", "selected_plugins.json")
 
 
def _rm(path):
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
    except Exception:
        traceback.print_exc()
 
 
def wipe():
    folder = get_data_dir()
    with notifications.LOCK:
        for name in DATA_FILES:
            _rm(folder / name)
        for p in folder.iterdir():
            if p.is_file() and p.name.startswith(("avatar", "alert")):
                _rm(p)
        root = Path(os.environ.get("NOTIFIO_ROOT", "."))
        for name in DEV_FILES:
            _rm(root / name)
    try:
        control.clear_missed()
    except Exception:
        traceback.print_exc()
    app_settings._cache = None
    notifications.RESTORED.clear()
    try:
        import downloader
        downloader.clear_finished()
    except Exception:
        pass
'''
 
NEW_FILES = {"Backend/app_reset.py": APP_RESET}
 
HOME_METHODS = r'''# wipe patch
    def _confirm_wipe(self,e):
        self.settings_box.visible=False
        self._safe_update()
 
        def go(ev):
            self._close_dialog(dlg)
            if self.on_wipe:
                self.on_wipe()
 
        dlg=ft.AlertDialog(
            title=ft.Text("Wipe all history?"),
            content=ft.Text("This deletes all every followed channels notifications and brings you to setup."),
            actions=[
                ft.TextButton("Cancel",on_click=lambda ev:self._close_dialog(dlg)),
                ft.TextButton("Wipe everything",on_click=go,style=ft.ButtonStyle(color="#ef6b6b")),
            ],
        )
        self._open_dialog(dlg)
 
    def _cards(self,items,empty):  # thumbnails patch
'''

HOME_SETUP_OLD= '''        return ft.Column([ft.Button("Redo setup",on_click=self._redo,height=38,style=BTN)])'''
HOME_SETUP_NEW= ''' 
wipe_style=ft.ButtonStyle(bgcolor="#ef6b6b",color="#0b0b0f",shape=ft.RoundedRectangleBorder(radius=19),padding=ft.Padding(22,0,22,0),text_style=ft.TextStyle(font_family="Inter-Medium",size=13,weight=ft.FontWeight.W_500))
        return ft.Column([
            ft.Button("Redo setup",on_click=self._redo,height=38,style=BTN),
            ft.Button("Wipe history",on_click=self._confirm_wipe,height=38,style=wipe_style),
            ft.Text("Removes all channels and history, then restarts setup.",size=11,color=S),
        ],spacing=12)'''

POLLER_FETCH_OLD = """            try:
                new = notifications.add_new(name, SOURCES[name]())
"""
POLLER_FETCH_NEW = """            try:
                fetched = SOURCES[name]()
                if self._stop.is_set():  # wipe patch: stopped while fetching
                    return
                new = notifications.add_new(name, fetched)
"""

EDITS = {
    "Backend/poller.py": ("wipe patch", [
        (POLLER_FETCH_OLD, POLLER_FETCH_NEW),
    ]),
    "UI/components/home_screen.py": ("_confirm_wipe", [
        ("        self.on_plugins_changed = None\n",
         "        self.on_plugins_changed = None\n        self.on_wipe = None\n"),
        (HOME_SETUP_OLD, HOME_SETUP_NEW),
        ("    def _cards(self,items,empty):  # thumbnails patch\n", "    " + HOME_METHODS),
    ]),
    "UI/ui.py": ("wipe_all", [
        ("        home.on_settings = redo_setup\n",
         "        home.on_settings = redo_setup\n        home.on_wipe = wipe_all  # wipe patch\n"),
        ("    saved = load_setup()\n    if saved:\n",
         "    def wipe_all():\n"
         "        stop_poller()\n"
         "        try:\n"
         "            import app_reset\n"
         "            app_reset.wipe()\n"
         "        except Exception:\n"
         "            _log(\"wipe failed:\\n\" + traceback.format_exc())\n"
         "        state[\"catchup\"] = True\n"
         "        redo_setup()\n\n"
         "    saved = load_setup()\n    if saved:\n"),
    ]),
}

def main():
    results,errors,created={}, [], {}

    for rel,text in NEW_FILES.items():
        path= ROOT/ rel
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            print(f"skip   {rel} (already exists)")
            continue
        try:
            compile(text,rel,"exec")
        except SyntaxError as e:
            errors.append(f"{rel}: would not compile ({e})")
        created[rel] = text

    for rel,(mark,edits) in EDITS.items():
        path=ROOT/rel
        if not path.is_file():
            errors.append(f"{rel}: file not found")
            continue
        text = path.read_text(encoding="utf-8")
        if mark in text:
            print(f"skip   {rel} (already patched)")
            continue
        for old,new in edits:
            n=text.count(old)
            if n!=1:
                errors.append(f"{rel}: expected 1 match, found {n} for: {old[:70]!r}")
                continue
            text=text.replace(old,new)
        if rel.endswith(".py"):
            try:
                compile(text,rel,"exec")
            except SyntaxError as e:
                errors.append(f"{rel}: result would not compile ({e})")
        results[rel]=text

    if errors:
        print("Nothing was changed.Problems:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    for rel,text in created.items():
        (ROOT / rel).write_text(text, encoding="utf-8")
        print(f"created {rel}")
    for rel,text in results.items():
        path=ROOT/ rel
        path.with_name(path.name + ".bak4").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        print(f"patched {rel}")
    print("Done.Restart Notifio")

if __name__ == "__main__":
    main()

