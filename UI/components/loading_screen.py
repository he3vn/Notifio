import flet as ft
from pathlib import Path

GRADIENT = ft.LinearGradient(
    begin=ft.Alignment(-1, 0),
    end=ft.Alignment(1, 0),
    colors=["#FFF9E6", "#FFF38A"],
    stops=[0.0, 1.0],
)

ASSET_PATH = Path(__file__).resolve().parents[2] / "Assets" / "SCR-20261019-ffwr.png"


class LoadingScreen(ft.Container):
    def __init__(self):
        super().__init__(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Image(
                            src=str(ASSET_PATH),
                            width=40,
                            height=40,
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
            gradient=GRADIENT,
            expand=True,
        )