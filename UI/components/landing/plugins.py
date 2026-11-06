import flet as ft
from .common import (BLUE, LOGOS, TITLE_FONT, GlossyButton,
                     border_all, layout, make_alignment, make_icon, play_click)

PLUGINS = [
    ("Twitch", "twitch.png"),
    ("Rumble", "rumble.png"),
    ("Youtube", "youtube.png"),
    ("News", "news.png"),
]


class PluginCard(ft.Container):
    W, H = 180, 200

    def __init__(self, name, filename, on_toggle):
        path = LOGOS / filename
        if path.is_file():
            logo = ft.Image(src=str(path), width=72, height=72, fit=ft.BoxFit.CONTAIN)
        else:
            logo = ft.Container(
                width=72, height=72, alignment=make_alignment(0, 0),
                content=ft.Text(name[0], size=44, color="white", weight=ft.FontWeight.W_700),
            )
        center = ft.Container(
            left=0, right=0, top=0, bottom=0,
            alignment=make_alignment(0, 0),
            content=ft.Column(
                [
                    logo,
                    ft.Text(name, size=18, weight=ft.FontWeight.W_600, color="white",
                            font_family=TITLE_FONT),
                ],
                spacing=14, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        check = ft.Container(right=10, top=10, visible=False,
                             content=make_icon("CHECK_CIRCLE_ROUNDED", 24, "white"))

        def clicked(e):
            play_click()
            on_toggle(name)

        super().__init__(
            width=self.W, height=self.H, border_radius=26,
            bgcolor="#40FFFFFF",
            border=border_all(1.5, "#80FFFFFF"),
            shadow=[ft.BoxShadow(blur_radius=18, color="#40000000", offset=ft.Offset(0, 6))],
            content=ft.Stack([center, check]),
            scale=1.0,
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_hover=self._hover,
            on_click=clicked,
        )
        self._check = check

    def set_selected(self, on: bool):
        self.bgcolor = "#80FFFFFF" if on else "#40FFFFFF"
        self.border = border_all(3, BLUE) if on else border_all(1.5, "#80FFFFFF")
        self.shadow = [ft.BoxShadow(
            blur_radius=26 if on else 18,
            color="#996b7fff" if on else "#40000000",
            offset=ft.Offset(0, 6),
        )]
        self._check.visible = on
        try:
            self.update()
        except Exception:
            pass

    def _hover(self, e):
        self.scale = 1.05 if str(e.data).lower() == "true" else 1.0
        try:
            self.update()
        except Exception:
            pass


class PluginsPage:
    def __init__(self, on_back, on_continue):
        self.selected = []
        self.on_back, self.on_continue = on_back, on_continue

        self.cards = {n: PluginCard(n, f, self._toggle) for n, f in PLUGINS}
        self.button = GlossyButton("Back", self._button_click, "ARROW_BACK_ROUNDED")

        block = ft.Column(
            [
                ft.Text("Select your plugins", size=56, weight=ft.FontWeight.W_700,
                        color="white", font_family=TITLE_FONT),
                ft.Text("Pick the sites you want to follow", size=24, italic=True,
                        color="white", font_family=TITLE_FONT),
                ft.Container(height=36),
                ft.Row(list(self.cards.values()), spacing=24, tight=True, wrap=True,
                       run_spacing=24, alignment=ft.MainAxisAlignment.CENTER),
            ],
            spacing=4, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.root, self.fg = layout(block, self.button, y=-0.1)

    def _toggle(self, name):
        if name in self.selected:
            self.selected.remove(name)
        else:
            self.selected.append(name)
        self.cards[name].set_selected(name in self.selected)
        self.sync_button()

    def sync_button(self):
        if self.selected:
            self.button.set("Continue", "ARROW_FORWARD_ROUNDED")
        else:
            self.button.set("Back", "ARROW_BACK_ROUNDED")

    def _button_click(self, e):
        if self.selected:
            self.on_continue(list(self.selected))
        else:
            self.on_back()