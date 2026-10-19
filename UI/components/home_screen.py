import flet as ft

BG = "#08090a"


class HomeScreen(ft.Container):
    def __init__(self, on_enter=None):
        super().__init__(
            bgcolor=BG,
            expand=True,
            on_click=lambda e: on_enter() if on_enter else None,
        )
