import flet as ft


class HomeScreen(ft.Container):
    #I might use this as a class place like  a little like setup wizard or ui.Py or js write all of the code here with ui which is quite long

    def __init__(self, name="", on_settings=None):
        super().__init__(bgcolor="#08090a", expand=True)
        self.on_settings = on_settings
        self.content = ft.Stack(expand=True, controls=[
            ft.Container(
                expand=True, alignment=ft.Alignment(0, 0),
                content=ft.Text("", size=20, color="#62666d", font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
            ),
            ft.IconButton(
                icon=ft.Icons.SETTINGS_OUTLINED, icon_color="#8a8f98", icon_size=20,
                tooltip="Redo setup", on_click=self._open_settings, right=16, top=16,
            ),
        ])

    def _open_settings(self, e):
        if self.on_settings:
            self.on_settings()