import flet as ft
from pathlib import Path

LOGO = Path(__file__).resolve().parents[2] / "Assets" / "Ferdium_1024x1024x32-recolored.png"


class LoadingScreen(ft.Container):
    """Minimal dark loading screen."""

    def __init__(self):
        super().__init__(
            bgcolor="#08090a", expand=True, alignment=ft.Alignment(0, 0),
            content=ft.Column(spacing=12, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Image(src=str(LOGO), width=100, height=100, border_radius=10),
                ft.Text("Loading...", size=13, color="#8a8f98", font_family="Inter-Medium", weight=ft.FontWeight.W_500),
            ]),
        )
