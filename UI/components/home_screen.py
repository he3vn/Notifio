import flet as ft
import json
from pathlib import Path
from .plugins import TOP,BOTTOM

LOGOS = Path(__file__).resolve().parents[2] / "Assets" / "logos"
FILES= dict(TOP+BOTTOM)

SELECTED_BG="#2b2d31"
HOVER_BG="#1c1d21"

class HomeScreen(ft.Container):

    def __init__(self, name="", on_settings=None, plugins=None):
        super().__init__(bgcolor="#08090a", expand=True)
        self.on_settings = on_settings
        self.plugins = plugins or []
        self.selected= None
        self.item_boxes= {}
        
        items= [self._item(n) for n in self.plugins]

        sidebar = ft.Container(
            width=220,
            bgcolor="#141516",
            padding=ft.Padding(16, 40, 16, 16),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=30,
                controls=[
                    ft.Text("Plugins",size=22,color="#f7f8f8",font_family="Inter-SemiBold",weight=ft.FontWeight.W_600),
                    ft.Container(height=8),
                    *items,
                ],
            ),
        )
        

        main_area = ft.Stack(expand=True, controls=[
            ft.Container(
                expand=True, alignment=ft.Alignment(0, 0),
                content=ft.Text("", size=20, color="#62666d", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
            ),
            ft.IconButton(
                icon=ft.Icons.SETTINGS_OUTLINED, icon_color="#8a8f98", icon_size=20,
                tooltip="Redo setup", on_click=self._open_settings, right=16, top=16,
            ),
        ])

        self.content = ft.Row(expand=True, spacing=0, controls=[sidebar, main_area])

    def _item(self,name):
        path=LOGOS /FILES.get(name,"")
        if path.is_file():
            logo=ft.Image(src=str(path),width=28,height=28,fit=ft.BoxFit.CONTAIN)
        else:
            logo=ft.Container(
                width=28,height=28,alignment=ft.Alignment(0,0),
                content=ft.Text(name[0],size=18,color="#8a8f98"),
            )
        box=ft.Container(
            padding=ft.Padding(8,6,8,6),border_radius=8,
            on_click=lambda e: self._select(name),
            on_hover=lambda e: self._hover(name,e),
            content=ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,controls=[
                logo,
                ft.Text(name,size=13,color="#f7f8f8",font_family="inter-Medium"),
            ]),
        )
        self.item_boxes[name]= box
        return box

    def _select(self,name):
        self.selected= None if self.selected == name else name
        for n, box in self.item_boxes.items():
            box.bgcolor= SELECTED_BG if n == self.selected else None
        try: self.update()
        except Exception: pass

    def _hover(self,name,e):
        if name == self.selected:
            return
        entering= e. data in (True,"true")
        e.control.bgcolor= HOVER_BG if entering else None
        e.control.update()

    def _open_settings(self, e):
        if self.on_settings:
            self.on_settings()