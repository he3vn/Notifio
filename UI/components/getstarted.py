import flet as ft
import subprocess, threading

H, S, F, A, B, V = "#f7f8f8", "#8a8f98", "#141516", "#171822", "#23252a", "#5e6ad2"


class Getstarted(ft.Container):
    """Page 1: Avatar + Name + Use Case picker."""

    def __init__(self, on_select=None):
        super().__init__()
        self.on_select, self.selected = on_select, "Streaming"
        self.avatar = ft.Container(
            width=38, height=38, border_radius=19, bgcolor=F,
            border=ft.Border.all(1, B), alignment=ft.Alignment(0, 0),
            content=ft.Icon(ft.Icons.PERSON_OUTLINE, size=20, color=S),
            on_click=self._pick, tooltip="Upload picture",
        )
        self.name_field = ft.TextField(
            border=ft.NoInputBorder(), hint_text="",
            text_style=ft.TextStyle(color=H, size=13, font_family="Inter"),
            content_padding=ft.Padding(12, 0, 12, 0),
        )
        name_box = ft.Container(
            content=self.name_field, bgcolor=F, border=ft.Border.all(1, B),
            border_radius=8, height=38, expand=True, alignment=ft.Alignment(0, 0),
        )
        self.card1 = self._card("Streaming", True)
        self.card2 = self._card("Streaming / Messaging", False)

        self.content = ft.Column(spacing=0, controls=[
            ft.Text("Set up your profile", size=22, color=H, font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
            ft.Text("Choose how you'll appear in Notifio", size=13, color=S),
            ft.Container(height=24),
            ft.Text("Name & picture", size=12, color=S, font_family="Inter-Medium"),
            ft.Container(height=4),
            ft.Row([self.avatar, name_box], spacing=10, width=360),
            ft.Container(height=16),
            ft.Text("Use case", size=12, color=S, font_family="Inter-Medium"),
            ft.Container(height=4),
            self.card1, ft.Container(height=4), self.card2,
        ])

    def _card(self, label, active):
        return ft.Container(
            width=360, height=44, border_radius=8, padding=ft.Padding(14, 0, 14, 0),
            border=ft.Border.all(1, V if active else B), bgcolor=A if active else F,
            on_click=lambda e: self._choose(label),
            content=ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if active else ft.Icons.RADIO_BUTTON_UNCHECKED, size=18, color=V if active else S),
                ft.Text(label, size=13, color=H, font_family="Inter-Medium"),
            ]),
        )

    def _choose(self, label):
        self.selected = label
        for card, lbl in [(self.card1, "Streaming"), (self.card2, "Streaming / Messaging")]:
            on = self.selected == lbl
            card.border, card.bgcolor = ft.Border.all(1, V if on else B), A if on else F
            card.content.controls[0] = ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if on else ft.Icons.RADIO_BUTTON_UNCHECKED, size=18, color=V if on else S)
        try: self.update()
        except Exception: pass
        if self.on_select: self.on_select(self.selected)

    def _pick(self, e):
        def _run():
            r = subprocess.run(
                ["osascript", "-e", 'POSIX path of (choose file of type {"public.image"} with prompt "Select Picture")'],
                capture_output=True, text=True)
            path = r.stdout.strip()
            if path:
                self.avatar.content = ft.Image(src=path, width=38, height=38, fit=ft.BoxFit.COVER, border_radius=19)
                try: self.avatar.update()
                except Exception: pass
        threading.Thread(target=_run, daemon=True).start()
