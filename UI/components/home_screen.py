from datetime import datetime
import flet as ft
from pathlib import Path
import notifications
from dexerto.feeds import FEEDS, ago
from .plugins import TOP, BOTTOM
from youtube import feeds as yt
from twitch import feeds as tw
from rumble import feeds as rb

ASSETS=Path(__file__).resolve().parents[2] /"Assets"
LOGOS= ASSETS/"logos"
BRAND_LOGO= ASSETS/"Ferdium_1024x1024x32-recolored.png"
BG_IMAGE=ASSETS/ "dot.webp"

FILES= dict(TOP+BOTTOM)
AVAILAIBLE=set(FEEDS) | {"Youtube", "Twitch", "Rumble"}
KIND_LABEL={"video":"Video","short":"Short","live":"LIVE","upcoming":"Upcoming"}
H, S = "#f7f8f8", "#8a8f98"
MAX_SHOWN=50
PANEL_BG="#D908090a"
PILL_BG = "#f7f8fb"
PILL_TEXT = "#0b0b0f"
PILL_SELECTED = "#dfe3ee"
BAR_H = 48
PAD = 6
BRAND_W = 40
ITEM_H = 36
ICON_W = 40
GAP = 2

def _anim(ms=260):
    return ft.Animation(ms,ft.AnimationCurve.EASE_OUT)

def _name_w(name):
    return max(64,int(len(name)*8+34))
            

class HomeScreen(ft.Container):
    def __init__(self, name="", on_settings=None, plugins=None):
        super().__init__(bgcolor="#08090a", expand=True)
        self.name = name
        self.on_settings = on_settings
        self.on_refresh = None
        self.on_plugins_changed = None
        self.plugins = list(plugins or [])
        self.selected = None
        self.item_boxes = {}
        self.last_status = ""
        self.adding = False
        self.nav_hover=False
        self.nav_items={}

        self.title=ft.Text("Notifications",size=22,color=H,font_family="Inter-Semibold",weight=ft.FontWeight.W_600)
        self.subtitle=ft.Text(f"Welcome back,{name}"if name else "",size=13,color=S)
        self.status=ft.Text("",size=11,color=S)
        self.remove_btn=ft.TextButton(
            "Remove plugin",visible=False,
            on_click=self._remove_selected,
            style=ft.ButtonStyle(color="#ef6b6b"),
            
        )
        self.yt_input=ft.TextField(
            hint_text="@handle or channel URL",dense=True,width=320,
            text_style=ft.TextStyle(size=13,color=H),
            on_submit=self._add_twitch,
        )
        self.tw_msg=ft.Text("",size=12,color=S)
        self.rb_input=ft.TextField(
            hint_text="channel name or rumble URL",dense=True,width=320,
            text_style=ft.TextStyle(size=13,color=H),
            on_submit=self._add_rumble,
        )
        self.rb_msg=ft.Text("",size=12,color=S)
        self.body=ft.Column(expand=True,spacing=8,scroll=ft.ScrollMode.AUTO)

        panel=ft.Container(
            expand=True,
            padding=ft.Padding(16,14,16,16),
            content=ft.Container(
                expand=True,bgcolor=PANEL_BG,border_radius=20,
                padding=ft.Padding(28,24,28,20),
                content=ft.Column(expand=True, spacing=0, controls=[
                    ft.Row(
                        [self.title, ft.Container(expand=True), self.remove_btn],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.subtitle,
                    ft.Container(height=4),
                    self.status,
                    ft.Container(height=12),
                    self.body,
                ]),
            ),
        )

        self.nav_row=ft.Row(spacing=GAP, tight=True,vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.nav_pill=ft.Container(
            height=BAR_H,border_radius=BAR_H /2,bgcolor=PILL_BG,
            padding=ft.Padding(PAD,0,PAD,0),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=_anim(260),
            on_hover=self._nav_hover,
            shadow=[ft.BoxShadow(blur_radius=14,color="#33000000",offset=ft.Offset(0, 4))],
            content=self.nav_row
        )
        self._rebuild_nav()

        def action(icon,tip,handler):
            return ft.IconButton(icon=icon,icon_color="#ffffff",icon_size=20,tooltip=tip,on_click=handler,width=40,height=40)
        actions=ft.Container(
            height=BAR_H,border_radius=BAR_H / 2,bgcolor="#000000",
            padding=ft.Padding(PAD,0,PAD,0),
            shadow=[ft.BoxShadow(blur_radius=14,color="#33000000",offset=ft.Offset(0, 4))],
            content=ft.Row(
                spacing=0,tight=True,vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    action(ft.Icons.ADD,"Add plugin",self._add_plugin),
                    action(ft.Icons.DELETE_OUTLINE,"Clear all notifications",self._clear),
                    action(ft.Icons.REFRESH,"Check now",self._manual_refresh),
                    action(ft.Icons.SEETINGS_OUTLINED,"Settings",self._toggle_settings),
                    ],
            )
        )

        top_bar=ft.Container(
            padding=ft.Padding(16,16,16,0),
            content=ft.Row(
                [self.nav_pill,ft.Containter(expand=True),actions],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,

            ),
        )
        