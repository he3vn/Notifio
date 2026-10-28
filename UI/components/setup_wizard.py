import flet as ft
from pathlib import Path
from .getstarted import Getstarted
from .plugins import Plugins
from .all_set import AllSet

BG = "#08090a"
ASSETS = Path(__file__).resolve().parents[2] / "Assets"
PAGE_IMAGES = [
    str(ASSETS / "mohammad-rahmani-N5bT5RctFZ8-unsplash.jpg"),
    str(ASSETS / "nubelson-fernandes-UcYBL5V0xWQ-unsplash.jpg"),
    str(ASSETS / "kevin-canlas-BHPGjYd4fp8-unsplash.jpg"),
]


class SetupWizard(ft.Container):
    def __init__(self, on_finish=None):
        super().__init__(expand=True, bgcolor=BG)
        self.on_finish, self.step, self.data = on_finish, 0, {"use_case": "Follow creators"}
        self.page_getstarted = Getstarted(lambda v: self.data.update({"use_case": v}))
        self.pages = [self.page_getstarted, Plugins(self.data), AllSet()]
        self.form = ft.Container(content=self.pages[0])
        self.dots = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.CENTER)
        self.hero = ft.Image(src=PAGE_IMAGES[0], fit=ft.BoxFit.COVER, opacity=0.35)
        self.btn_back = ft.TextButton("Back", visible=False, on_click=self._prev,
            style=ft.ButtonStyle(color="#8a8f98", text_style=ft.TextStyle(font_family="Inter-Medium", size=13)))
        self.btn_next = ft.Button("Continue", on_click=self._next, height=36,
            style=ft.ButtonStyle(bgcolor="#28282c", color="#f7f8f8", shape=ft.RoundedRectangleBorder(radius=18),
                padding=ft.Padding(18, 0, 18, 0), text_style=ft.TextStyle(font_family="Inter-Medium", size=13, weight=ft.FontWeight.W_500)))
        self._sync()

        left = ft.Container(expand=6, bgcolor=BG, padding=ft.Padding(90, 40, 40, 10), content=ft.Column(expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.START, controls=[
                ft.Container(height=35), self.form, ft.Container(height=16),
                ft.Container(width=360, content=ft.Row([self.btn_back, self.btn_next], alignment=ft.MainAxisAlignment.END, spacing=8)),
                ft.Container(expand=True),
                ft.Container(width=360, content=self.dots, alignment=ft.Alignment(0, 0), padding=ft.Padding(0, 0, 0, 24)),
            ]))
        right = ft.Container(expand=4, bgcolor=BG, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, content=self.hero)
        self.content = ft.Row([left, right], expand=True, spacing=0)

    def _sync(self):
        self.form.content, self.hero.src = self.pages[self.step], PAGE_IMAGES[self.step]
        self.dots.controls = [ft.Container(width=22 if i == self.step else 6, height=6, border_radius=3,
            bgcolor="#f7f8f8" if i == self.step else "#34343a") for i in range(len(self.pages))]
        self.btn_back.visible = self.step > 0
        self.btn_next.text = "Finish" if self.step == len(self.pages) - 1 else "Continue"

    def _next(self, e):
        if self.step < len(self.pages) - 1:
            self.step += 1; self._sync()
            if self.step==1:
                self.pages[1].refresh()
            try: self.page.update()
            except Exception: pass
        elif self.on_finish:
            self.data["name"]= self.page_getstarted.name_field.value
            self.on_finish(self.data)

    def _prev(self, e):
        if self.step > 0:
            self.step -= 1; self._sync()
            try: self.page.update()
            except Exception: pass
