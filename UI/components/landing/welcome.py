import flet as ft
from .common import GlossyButton, TITLE_FONT, layout

TITLE = "Notifio"
SUBTITLE = "Your Notification center"


class WelcomePage:
    def __init__(self, on_start):
        self.button = GlossyButton("Get started", lambda e: on_start())
        block = ft.Column(
            [
                ft.Text(TITLE, size=120, weight=ft.FontWeight.W_700, color="white",
                        font_family=TITLE_FONT),
                ft.Text(SUBTITLE, size=34, italic=True, color="white",
                        font_family=TITLE_FONT, text_align=ft.TextAlign.CENTER),
            ],
            spacing=0, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.root, self.fg = layout(block, self.button)