import flet as ft
import subprocess, threading

H, S, F, A, B, V = "#f7f8f8", "#8a8f98", "#141516", "#171822", "#23252a", "#5e6ad2"

OPTIONS = ["Follow creators", "Stay informed"]
RECOMMENDED = "Follow creators"


class Getstarted(ft.Container):
   

    def __init__(self, on_select=None):
        super().__init__()
        self.on_select, self.selected = on_select, OPTIONS[0]
        self.avatar = ft.Container(
            width=38, height=38, border_radius=19, bgcolor=F,
            border=ft.Border.all(1, B), alignment=ft.Alignment(0, 0),
            content=ft.Icon(ft.Icons.PERSON_OUTLINE, size=20, color=S),
            on_click=self._pick, tooltip="Upload picture",
        )
        self.name_field = ft.TextField(
            dense=True,
            expand=True,
            filled=False,
            border=ft.NoInputBorder(),
            hint_text="Your name",
            hint_style=ft.TextStyle(color=S, size=14, font_family="Inter"),
            text_style=ft.TextStyle(color=H, size=14, font_family="Inter"),
            cursor_color=V,
            cursor_height=16,
            content_padding=ft.Padding(12, 10, 12, 10),
        )
        name_box = ft.Container(
            content=self.name_field, bgcolor=F, border=ft.Border.all(1, B),
            border_radius=8, height=38, expand=True, alignment=ft.Alignment(0, 0),
        )
        self.card1 = self._card(OPTIONS[0], True)
        self.card2 = self._card(OPTIONS[1], False)

        self.content = ft.Column(spacing=0, controls=[
            ft.Text("Set up your profile", size=22, color=H, font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
            ft.Text("Choose how you'll appear in Notifio", size=13, color=S),
            ft.Container(height=24),
            ft.Text("Name & picture", size=12, color=S, font_family="Inter-Medium"),
            ft.Container(height=4),
            ft.Row([self.avatar, name_box], spacing=10, width=360),
            ft.Container(height=16),
            ft.Text("What do you want to do?", size=12, color=S, font_family="Inter-Medium"),
            ft.Container(height=4),
            self.card1, ft.Container(height=4), self.card2,
        ])

    def _badge(self):
        return ft.Container(
            padding=ft.Padding(8, 2, 8, 2), border_radius=10,
            border=ft.Border.all(1, V),
            content=ft.Text("Recommended", size=10, color=V, font_family="Inter-Medium"),
        )

    def _card(self, label, active):
        controls = [
            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if active else ft.Icons.RADIO_BUTTON_UNCHECKED, size=18, color=V if active else S),
            ft.Text(label, size=13, color=H, font_family="Inter-Medium", expand=True),
        ]
        if label == RECOMMENDED:
            controls.append(self._badge())
        return ft.Container(
            width=360, height=44, border_radius=8, padding=ft.Padding(14, 0, 14, 0),
            border=ft.Border.all(1, V if active else B), bgcolor=A if active else F,
            on_click=lambda e: self._choose(label),
            content=ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=controls),
        )

    def _choose(self, label):
        self.selected = label
        for card, lbl in zip([self.card1, self.card2], OPTIONS):
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