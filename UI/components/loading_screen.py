import flet as ft
from pathlib import Path

BG = "#08090a"
ASSET_PATH = Path(__file__).resolve().parents[2] / "Assets" / "Ferdium_1024x1024x32-recolored.png"


class LoadingScreen(ft.Container):
    def __init__(self):
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Image(
                            src=str(ASSET_PATH),
                            width=100,
                            height=100,
                            border_radius=10,
                        ),
                        ft.Container(height=12),
                        ft.Text("Loading...", size=13, color="#6b7280"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                ),
                alignment=ft.Alignment(0, 0),
                expand=True,
            ),
            bgcolor=BG,
            expand=True,
        )