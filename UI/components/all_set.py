import flet as ft


class AllSet(ft.Container):
    """Page 3: Final confirmation screen."""

    def __init__(self):
        super().__init__()
        self.content = ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.START, controls=[
            ft.Text("All set", size=22, color="#f7f8f8", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
            ft.Text("You're all ready to start using Notifio", size=13, color="#8a8f98"),
            ft.Container(height=24),
        ])
