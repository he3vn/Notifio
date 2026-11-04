
from pathlib import Path
import flet as ft
ASSETS = Path(__file__).resolve().parents[3] / "Assets"
LOGOS = ASSETS / "logos"

TITLE_FONT = "Helvetica Neue"
BLUE = "#3434d6"



def make_alignment(x: float, y: float):
    try:
        return ft.Alignment(x, y)
    except AttributeError:  # older flet
        return ft.alignment.Alignment(x, y)


def border_all(width, color):
    try:
        return ft.Border.all(width, color)  # newer flet
    except AttributeError:
        return ft.border.all(width, color)  # older flet


def make_icon(name, size, color):
    """Icon control, or None if this flet version lacks it."""
    try:
        icons = getattr(ft, "Icons", None) or ft.icons
        return ft.Icon(getattr(icons, name), size=size, color=color)
    except Exception:
        return None


def make_label(text, color, glow):
    """Button text with an optional soft glow."""
    weight = ft.FontWeight.W_600
    try:
        if glow:
            shadow = ft.BoxShadow(blur_radius=6, color=glow, offset=ft.Offset(0, 0))
            return ft.Text(text, style=ft.TextStyle(size=18, weight=weight, color=color, shadow=shadow))
    except Exception:
        pass
    return ft.Text(text, size=18, weight=weight, color=color)

class GlossyButton(ft.Container):
    WIDTH, HEIGHT = 244, 54
    TEXT = "#0a0a16"
    GLOW = "#D9FFFFFF"

    def __init__(self, text, on_click, icon_name="ARROW_FORWARD_ROUNDED"):
        row = ft.Row(
            self._items(text, icon_name),
            spacing=9, tight=True, alignment=ft.MainAxisAlignment.CENTER,
        )
        label_layer = ft.Container(
            left=0, right=0, top=0, bottom=0,
            alignment=make_alignment(0, 0),
            content=row,
        )
        gloss = ft.Container(
            left=14, right=14, top=3, height=22, border_radius=20,
            gradient=ft.LinearGradient(
                begin=make_alignment(0, -1), end=make_alignment(0, 1),
                colors=["#B3FFFFFF", "#14FFFFFF"],
            ),
        )
        body = ft.Container(
            width=self.WIDTH, height=self.HEIGHT, border_radius=self.HEIGHT / 2,
            border=border_all(1.5, BLUE),
            gradient=ft.LinearGradient(
                begin=make_alignment(0, -1), end=make_alignment(0, 1),
                colors=["#dcedff", "#a3cdff", "#7fb7ff", "#8fc2ff"],
                stops=[0.0, 0.45, 0.55, 1.0],
            ),
            shadow=[
                ft.BoxShadow(blur_radius=18, color="#6b7f90ff", offset=ft.Offset(0, 4)),
                ft.BoxShadow(blur_radius=3, color="#40000000", offset=ft.Offset(0, 1)),
            ],
            content=ft.Stack([gloss, label_layer]),
        )
        super().__init__(
            content=body,
            scale=1.0,
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=on_click,
            on_hover=self._hover,
        )
        self._row = row

    @classmethod
    def _items(cls, text, icon_name):
        items = []
        ic = make_icon(icon_name, 20, cls.TEXT)
        if ic is not None:
            items.append(ic)
        items.append(make_label(text, cls.TEXT, cls.GLOW))
        return items

    def set(self, text, icon_name):
        """Change the label + icon (e.g. Back -> Continue)."""
        self._row.controls = self._items(text, icon_name)
        try:
            self.update()
        except Exception:
            pass

    def _hover(self, e):
        self.scale = 1.05 if str(e.data).lower() == "true" else 1.0
        try:
            self.update()
        except Exception:
            pass


def layout(center_content, button, y=-0.15):
    """Returns (root, fg). `fg` is the part that moves with the parallax."""
    fg = ft.Container(expand=True, alignment=make_alignment(0, y), content=center_content)
    root = ft.Container(
        expand=True,
        content=ft.Column(
            expand=True, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                fg,
                ft.Container(height=150, alignment=make_alignment(0, 0), content=button),
            ],
        ),
    )
    return root, fg