import flet as ft
from .common import (GlossyButton, TITLE_FONT, border_all, layout,
                     make_alignment, make_icon)

GITHUB = "https://github.com/he3vn/Notifio"
HACKCLUB = "https://hackclub.com/"


class LinkButton(ft.Container):
    TEXT = "#1d1d1f"

    def __init__(self, text, url, icon_name):
        items = []
        ic = make_icon(icon_name, 20, self.TEXT)
        if ic is not None:
            items.append(ic)
        items.append(ft.Text(text, size=17, color=self.TEXT, weight=ft.FontWeight.W_500))
        super().__init__(
            content=ft.Row(items, spacing=9, tight=True,
                           alignment=ft.MainAxisAlignment.CENTER),
            width=250, height=46, border_radius=23,
            alignment=make_alignment(0, 0),
            border=border_all(1, "#b5b5b5"),
            gradient=ft.LinearGradient(
                begin=make_alignment(0, -1), end=make_alignment(0, 1),
                colors=["#ffffff", "#e4e4e4"],
            ),
            shadow=[ft.BoxShadow(blur_radius=8, color="#40000000", offset=ft.Offset(0, 2))],
            url=url,
            scale=1.0,
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_hover=self._hover,
        )

    def _hover(self, e):
        self.scale = 1.05 if str(e.data).lower() == "true" else 1.0
        try:
            self.update()
        except Exception:
            pass


def _caption(text):
    return ft.Text(text, size=22, italic=True, color="white", font_family=TITLE_FONT)


class DonePage:
    def __init__(self, on_finish):
        self.button = GlossyButton("Continue", lambda e: on_finish(),
                                   "ARROW_FORWARD_ROUNDED")
        block = ft.Column(
            [
                ft.Text("All set!", size=96, weight=ft.FontWeight.W_700,
                        color="white", font_family=TITLE_FONT),
                ft.Container(height=24),
                _caption("Star my project on GitHub!"),
                LinkButton("Notifio on GitHub", GITHUB, "STAR_ROUNDED"),
                ft.Container(height=14),
                _caption("Check out Hack Club"),
                LinkButton("hackclub.com", HACKCLUB, "OPEN_IN_NEW_ROUNDED"),
            ],
            spacing=8, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.root, self.fg = layout(block, self.button, y=-0.1)