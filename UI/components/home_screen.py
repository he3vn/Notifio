import flet as ft
from pathlib import Path

GRADIENT = ft.LinearGradient(
    begin=ft.Alignment(-1, 0),
    end=ft.Alignment(1, 0),
    colors=["#FFF9E6", "#FFF38A"],
    stops=[0.0, 1.0],
)

ASSET_PATH = Path(__file__).resolve().parents[2] / "Assets" / "SCR-20261019-ffwr.png"


class HomeScreen(ft.Container):
    def __init__(self, on_enter=None):
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Image(
                            src=str(ASSET_PATH),
                            width=44,
                            height=44,
                            border_radius=11,
                        ),
                        ft.Container(height=16),
                        ft.Text(
                            "Notifio",
                            size=22,
                            weight=ft.FontWeight.W_600,
                            color="#1c1601",
                        ),
                        ft.Container(height=6),
                        ft.Text(
                            "Your notification hub",
                            size=14,
                            color="#6b7280",
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=0,
                ),
                alignment=ft.Alignment(0, -0.05),
                expand=True,
                on_click=lambda e: on_enter() if on_enter else None,
            ),
            gradient=GRADIENT,
            expand=True,
        )
