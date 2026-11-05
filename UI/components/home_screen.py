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