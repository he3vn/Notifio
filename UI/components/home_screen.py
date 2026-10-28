from datetime import datetime
import flet as ft
from pathlib import Path
import notifications
from dexerto.feeds import FEEDS, ago
from .plugins import TOP, BOTTOM

LOGOS = Path(__file__).resolve().parents[2] / "Assets" / "logos"
FILES = dict(TOP + BOTTOM)

SELECTED_BG = "#2b2d31"
HOVER_BG = "#1c1d21"
H, S, V = "#f7f8f8", "#8a8f98", "#5e6ad2"
MAX_SHOWN=50


class HomeScreen(ft.Container):

    def __init__(self, name="", on_settings=None, plugins=None):
        super().__init__(bgcolor="#08090a", expand=True)
        self.name = name
        self.on_settings = on_settings
        self.on_refresh = None  # ui.py connects this to the poller
        self.plugins = plugins or []
        self.selected = None
        self.item_boxes = {}
        self.last_status=""

        items = [self._item(n) for n in self.plugins]

        sidebar = ft.Container(
            width=220,
            bgcolor="#141516",
            padding=ft.Padding(16, 40, 16, 16),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=30,
                controls=[
                    ft.Text("Plugins", size=22, color=H, font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
                    ft.Container(height=8),
                    *items,
                ],
            ),
        )

        self.title = ft.Text("Notifications", size=22, color=H, font_family="Inter-SemiBold", weight=ft.FontWeight.W_600)
        self.subtitle = ft.Text(f"Welcome back, {name}" if name else "", size=13, color=S)
        self.status = ft.Text("Checking...", size=11, color=S)
        self.body = ft.Column(expand=True, spacing=8, scroll=ft.ScrollMode.AUTO)

        main_area = ft.Stack(expand=True, controls=[
            ft.Container(
                expand=True,
                padding=ft.Padding(32, 40, 32, 24),
                content=ft.Column(expand=True, spacing=0, controls=[
                    self.title,
                    self.subtitle,
                    ft.Container(height=4),
                    self.status,
                    ft.Container(height=12),
                    self.body,
                ]),
            ),
                        ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE, icon_color=S, icon_size=20,
                tooltip="Clear all notifications", on_click=self._clear, right=96, top=16,
            ),
            ft.IconButton(
                icon=ft.Icons.REFRESH, icon_color=S, icon_size=20,
                tooltip="Check now", on_click=self._manual_refresh, right=56, top=16,
            ),
            ft.IconButton(
                icon=ft.Icons.SETTINGS_OUTLINED, icon_color=S, icon_size=20,
                tooltip="Redo setup", on_click=self._open_settings, right=16, top=16,
            ),
        ])

        self.content = ft.Row(expand=True, spacing=0, controls=[sidebar, main_area])
        self._render()  # show saved history immediately

    
    def _item(self, name):
        path = LOGOS / FILES.get(name, "")
        if path.is_file():
            logo = ft.Image(src=str(path), width=28, height=28, fit=ft.BoxFit.CONTAIN)
        else:
            logo = ft.Container(
                width=28, height=28, alignment=ft.Alignment(0, 0),
                content=ft.Text(name[0], size=18, color=S),
            )
        box = ft.Container(
            padding=ft.Padding(8, 6, 8, 6), border_radius=8,
            on_click=lambda e: self._select(name),
            on_hover=lambda e: self._hover(name, e),
            content=ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                logo,
                ft.Text(name, size=13, color=H, font_family="Inter-Medium"),
            ]),
        )
        self.item_boxes[name] = box
        return box

    def _select(self, name):
        self.selected = None if self.selected == name else name
        for n, box in self.item_boxes.items():
            box.bgcolor = SELECTED_BG if n == self.selected else None
        self._render()
        try: self.update()
        except Exception: pass

    def _hover(self, name, e):
        if name == self.selected:
            return
        entering = e.data in (True, "true")
        e.control.bgcolor = HOVER_BG if entering else None
        e.control.update()

    
    def _render(self):
        self.title.value = self.selected or "Notifications"
        
        if not self.selected:
            self.status.value=""
            self.body.controls=[ft.Text("Select a plugin to view the notifications",size=13,color=S)]
            return
        
        self.status.value=self.last_status
        items=[i for i in notifications.load() if i.get("plugin") ==self.selected][:MAX_SHOWN]
        
        if items:
            self.body.controls = [self._row(i) for i in items]
        elif self.selected and self.selected not in FEEDS:
            self.body.controls = [ft.Text("This source isn't available yet.", size=13, color=S)]
        else:
            self.body.controls = [ft.Text("No notifications yet.", size=13, color=S)]

    def _row(self, item):
        delete=ft.IconButton(
            icon=ft.Icons.CLOSE, icon_size=16, icon_color=S,
            tooltip="Remove",opacity=0,
            on_click=lambda e: self._delete(item),
        )

        def hover(e):
            delete.opacity=1 if e.data in (True,"true")else 0
            try: delete.update()
            except Exception: pass

        return ft.Container(
            padding=ft.Padding(14,4,6,4),border_radius=8,bgcolor="#141516",
            on_hover=hover,
            content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER,controls=[
                ft.Container(
                    url=item["link"],expand=True,
                    padding=ft.Padding(0,6,0,6),
                    content=ft.Column(spacing=2,controls=[
                        ft.Text(item["title"],size=13,color=H,font_family="Inter-Medium"),
                        ft.Text(f'{item["source"]} · {ago(item["ts"])}',size=11,color=S),
                    ]),   
                ),
                delete,
            ]),
        )

    def _delete(self,item):
        notifications.remove(item["link"])
        self._render()
        try: self.update()
        except Exception: pass

    def _clear(self,e):
        notifications.clear_all()
        self._render()
        try: self.update()
        except Exception: pass

   
    def on_poll(self, added, failed):
        now = datetime.now().strftime("%H:%M")
        self.last_status = f"Couldn't refresh at {now}" if failed else f"Last checked {now}"
        if self.selected:
            self._render()
        try: self.update()
        except Exception: pass

    def _manual_refresh(self, e):
        if self.on_refresh:
            self.last_status = "Checking..."
            self._render()
            try: self.update()
            except Exception: pass
            self.on_refresh()

    def _open_settings(self, e):
        if self.on_settings:
            self.on_settings()