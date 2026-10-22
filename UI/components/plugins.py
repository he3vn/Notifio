import flet as ft


class Plugins(ft.Container):
    """Page 2: Configure your plugins."""

    def __init__(self):
        super().__init__()
        self.content = ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.START, controls=[
            ft.Text("Configure your plugins", size=22, color="#f7f8f8", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
            ft.Text("Select and organize the plugins you want to enable", size=13, color="#8a8f98"),
            ft.Container(height=24),
            # Add your boxes below
        ])
