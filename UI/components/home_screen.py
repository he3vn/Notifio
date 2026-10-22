import flet as ft


class HomeScreen(ft.Container):
    """Clean black screen displayed after setup."""

    def __init__(self, name=""):
        super().__init__(
            bgcolor="#08090a", expand=True, alignment=ft.Alignment(0, 0),
            content=ft.Text("Notifio", size=20, color="#62666d", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
        )
