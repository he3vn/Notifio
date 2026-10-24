import json
import flet as ft
from pathlib import Path
from storage import get_data_dir

LOGOS = Path(__file__).resolve().parents[2] / "Assets" / "logos"
SAVE_FILE = get_data_dir() / "selected_plugins.json"
DEV_FILE = Path(__file__).resolve().parents[2] / "selected_plugins.json"

NORMAL = "#3a3d44"
SELECTED = "#5e6ad2"

TOP = [
    ("Twitch", "twitch.png"),
    ("Rumble", "rumble.png"),
    ("Youtube", "youtube.png"),
    ("X", "x.png"),
]
BOTTOM = [
    ("News", "news.png"),
    ("Patreon", "patreon.png"),
    ("Slack", "slack.png"),
    ("Facebook", "facebook.png"),
]


class Plugins(ft.Container):

    def __init__(self, data):
        super().__init__()
        self.data = data
        self.boxes = {}        # name -> box control
        self.applied = None    # which use case we last pre-selected for
        self.data.setdefault("plugins", [])

        self.top_boxes = [self._box(*p) for p in TOP]
        self.bottom_boxes = [self._box(*p) for p in BOTTOM]

        self.content = ft.Column(
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Text("Configure your plugins", size=22, color="#f7f8f8", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
                ft.Text("Select and organize the plugins you want to enable", size=13, color="#8a8f98"),
                ft.Container(height=50),
                ft.Text("Recommended", size=22, color="#f7f8f8", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
                ft.Container(height=24),
                ft.Row(controls=self.top_boxes, spacing=10),
                ft.Container(height=10),
                ft.Row(controls=self.bottom_boxes, spacing=10),
            ],
        )

    def _logo(self, filename, name):
        path = LOGOS / filename
        if path.exists():
            return ft.Image(src=str(path), width=40, height=40, fit=ft.BoxFit.CONTAIN)
        return ft.Container(
            width=40, height=40, alignment=ft.Alignment(0, 0),
            content=ft.Text(name[0], size=28, color="#8a8f98", font_family="Inter-Bold", weight=ft.FontWeight.W_700),
        )

    def _box(self, name, filename):
        box = ft.Container(
            width=90,
            height=130,
            bgcolor="#26282c",
            border_radius=12,
            border=ft.Border.all(1, NORMAL),
            on_click=lambda e: self._toggle(name),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    self._logo(filename, name),
                    ft.Text(name, size=12, color="#f7f8f8", font_family="Inter-Medium"),
                ],
            ),
        )
        self.boxes[name] = box
        return box

    def _toggle(self, name):
        chosen = self.data["plugins"]
        if name in chosen:
            chosen.remove(name)
        else:
            chosen.append(name)
        self._restyle()
        self._save()
        try: self.update()
        except Exception: pass

    def _restyle(self):
        for name, box in self.boxes.items():
            if name in self.data["plugins"]:
                box.border = ft.Border.all(2, SELECTED)
            else:
                box.border = ft.Border.all(1, NORMAL)

    def _save(self):
        try:
            SAVE_FILE.write_text(json.dumps(self.data["plugins"]))
        except Exception:
            try:
                DEV_FILE.write_text(json.dumps(self.data["plugins"]))
            except Exception:
                pass

    def refresh(self):
        use = self.data["use_case"]
        if use != self.applied:          # only pre-select when the category changed
            row = TOP if use == "Follow creators" else BOTTOM
            self.data["plugins"][:] = [name for name, _ in row]
            self.applied = use
            self._restyle()
            self._save()