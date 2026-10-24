import flet as ft
from pathlib import Path

DONATIONS = Path(__file__).resolve().parents[2] / "Assets" / "donations"


class AllSet(ft.Container):
    """Page 3: All set + donation."""

    def __init__(self):
        super().__init__()
        self.content = ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.START, controls=[
            ft.Text("All set", size=22, color="#f7f8f8", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
            ft.Text("You're all ready to start using Notifio", size=13, color="#8a8f98"),
            ft.Container(height=30),
            ft.Column(
                width=360,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text("Donate to support!", size=22, color="#5e6ad2", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Image(src=str(DONATIONS / "bitcoin.png"), width=320, height=320),
                            ft.Image(src=str(DONATIONS / "solana.png"), width=320, height=320),
                        ],
                    ),
                ],
            ),
        ])