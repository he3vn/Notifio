import flet as ft
from .common import GlossyButton,layout

class DonePage:
    def __init__(self,on_back):
        self.button = GlossyButton("Back", lambda e: on_back(), "ARROW_BACK_ROUNDED")
        self.root,self.fg=layout(ft.Container(), self.button)