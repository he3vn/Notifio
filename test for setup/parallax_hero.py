"""
Notifio landing (Flet): mouse parallax + glossy "Get started" button + a second page.

  * Page 1: background image, centred title, glossy button.
  * Click "Get started" -> page 2 (same background image, the title/button fade out).
  * Mouse parallax (lerp 0.15) shifts the background slightly, like the Shopify hero.

Setup:  pip install flet
Run:    python parallax_hero.py
"""
from __future__ import annotations

import asyncio
import os
import time

import flet as ft

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
IMAGE = "/Users/papemalicksene/Downloads/doc3.jpg"   # used for BOTH pages

# title text
TITLE = "Notifio"
SUBTITLE = "Your Notification center"
TITLE_FONT = "Helvetica Neue"   # macOS system font (try "Avenir Next", "Georgia")

# button
BUTTON_TEXT = "Get started"
BUTTON_STYLE = "mac"            # "mac" (glossy blue) or "windows" (white pill)
BUTTON_ICON = True              # small arrow on the left of the label

# parallax
LERP = 0.15
PARALLAX = 0.03
BG_DEPTH, FG_DEPTH = 0.3, 1.0


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def make_alignment(x: float, y: float):
    try:
        return ft.Alignment(x, y)
    except AttributeError:  # older flet
        return ft.alignment.Alignment(x, y)


def border_all(width, color):
    try:
        return ft.Border.all(width, color)   # newer flet
    except AttributeError:
        return ft.border.all(width, color)   # older flet


def _icon(name, size, color):
    """Icon control, or None if this flet version lacks it."""
    try:
        icons = getattr(ft, "Icons", None) or ft.icons
        return ft.Icon(getattr(icons, name), size=size, color=color)
    except Exception:
        return None


def _label(text, color, glow):
    """Button text, with a soft glow like the 'download for mac' label."""
    weight = ft.FontWeight.W_600
    try:
        if glow:
            shadow = ft.BoxShadow(blur_radius=6, color=glow, offset=ft.Offset(0, 0))
            return ft.Text(text, style=ft.TextStyle(size=18, weight=weight, color=color, shadow=shadow))
    except Exception:
        pass
    return ft.Text(text, size=18, weight=weight, color=color)


BUTTON_STYLES = {
    "mac": dict(
        width=244, height=54,
        border=("#3434d6", 1.5),
        gradient=["#dcedff", "#a3cdff", "#7fb7ff", "#8fc2ff"],
        stops=[0.0, 0.45, 0.55, 1.0],
        gloss=["#B3FFFFFF", "#14FFFFFF"],
        shadows=[("#6b7f90ff", 18, (0, 4)), ("#40000000", 3, (0, 1))],
        text="#0a0a16", glow="#D9FFFFFF", icon="#0a0a16",
    ),
    "windows": dict(
        width=244, height=54,
        border=("#c4c4c4", 1.0),
        gradient=["#ffffff", "#f4f4f4", "#e3e3e3"],
        stops=[0.0, 0.5, 1.0],
        gloss=None,
        shadows=[("#2e000000", 10, (0, 3)), ("#1a000000", 2, (0, 1))],
        text="#1b1b1b", glow=None, icon="#1b1b1b",
    ),
}


def make_button(text, on_click, icon_name="ARROW_FORWARD_ROUNDED"):
    """Glossy pill button modelled on the 'download for mac' / 'download for windows' buttons."""
    s = BUTTON_STYLES.get(BUTTON_STYLE, BUTTON_STYLES["mac"])

    row_items = []
    if BUTTON_ICON:
        ic = _icon(icon_name, 20, s["icon"])
        if ic is not None:
            row_items.append(ic)
    row_items.append(_label(text, s["text"], s["glow"]))

    content = ft.Container(
        left=0, right=0, top=0, bottom=0,
        alignment=make_alignment(0, 0),
        content=ft.Row(row_items, spacing=9, tight=True, alignment=ft.MainAxisAlignment.CENTER),
    )

    children = []
    if s["gloss"]:
        children.append(
            ft.Container(
                left=14, right=14, top=3, height=22, border_radius=20,
                gradient=ft.LinearGradient(
                    begin=make_alignment(0, -1), end=make_alignment(0, 1), colors=s["gloss"],
                ),
            )
        )
    children.append(content)

    body = ft.Container(
        width=s["width"], height=s["height"], border_radius=s["height"] / 2,
        border=border_all(s["border"][1], s["border"][0]),
        gradient=ft.LinearGradient(
            begin=make_alignment(0, -1), end=make_alignment(0, 1),
            colors=s["gradient"], stops=s["stops"],
        ),
        shadow=[ft.BoxShadow(blur_radius=b, color=c, offset=ft.Offset(*o)) for c, b, o in s["shadows"]],
        content=ft.Stack(children),
    )

    btn = ft.Container(
        content=body,
        scale=1.0,
        animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        on_click=on_click,
    )

    def on_hover(e):
        btn.scale = 1.05 if str(e.data).lower() == "true" else 1.0
        btn.update()

    btn.on_hover = on_hover
    return btn


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
def main(page: ft.Page):
    page.title = "Notifio"
    page.padding = 0
    page.bgcolor = "#000000"

    if not os.path.exists(IMAGE):
        page.add(ft.Text(f"Image not found: {IMAGE}", color="red"))
        return

    fit_enum = getattr(ft, "BoxFit", None) or ft.ImageFit  # renamed in newer flet
    win = {"w": page.width or 1280, "h": page.height or 720}

    # --- shared background (same image on both pages) ---
    bg_img = ft.Image(src=IMAGE, fit=fit_enum.COVER, width=win["w"], height=win["h"],
                      gapless_playback=True)
    bg = ft.Container(expand=True, scale=1.12, content=bg_img)  # oversize so edges never show

    # --- page 1: title + button ---
    title = ft.Container(
        expand=True,
        alignment=make_alignment(0, -0.15),
        content=ft.Column(
            [
                ft.Text(TITLE, size=120, weight=ft.FontWeight.W_700, color="white",
                        font_family=TITLE_FONT),
                ft.Text(SUBTITLE, size=34, italic=True, color="white",
                        font_family=TITLE_FONT, text_align=ft.TextAlign.CENTER),
            ],
            spacing=0,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    # --- page 2: same background, with a Back button ---
    def go_page2(e):
        page1.visible = False
        page2.visible = True
        page.update()

    def go_page1(e):
        page2.visible = False
        page1.visible = True
        page.update()

    page1 = ft.Container(
        expand=True,
        visible=True,
        content=ft.Stack([
            title,
            ft.Container(
                expand=True,
                alignment=make_alignment(0, 0.82),
                content=make_button(BUTTON_TEXT, go_page2),
            ),
        ], expand=True),
    )

    page2 = ft.Container(
        expand=True,
        visible=False,
        content=ft.Container(
            expand=True,
            alignment=make_alignment(0, 0.82),
            content=make_button("Back", go_page1, icon_name="ARROW_BACK_ROUNDED"),
        ),
    )

    # --- pointer / parallax ---
    target = {"x": 0.0, "y": 0.0}
    current = {"x": 0.0, "y": 0.0}

    def on_hover(e):
        w = page.width or 1
        h = page.height or 1
        lx = getattr(e, "local_x", None)
        ly = getattr(e, "local_y", None)
        if lx is None:  # newer flet
            lx, ly = e.local_position.x, e.local_position.y
        target["x"] = max(-1.0, min(1.0, lx / w * 2 - 1))
        target["y"] = max(-1.0, min(1.0, ly / h * 2 - 1))

    def on_exit(e):
        target["x"] = target["y"] = 0.0

    async def loop():
        last = time.perf_counter()
        while True:
            now = time.perf_counter()
            dt = now - last
            last = now

            # keep the background exactly window-sized (handles resizing)
            w, h = page.width, page.height
            if w and h and (w != win["w"] or h != win["h"]):
                win["w"], win["h"] = w, h
                bg_img.width, bg_img.height = w, h

            # smoothed pointer (frame-rate independent form of cur += (target-cur)*0.15)
            k = 1 - (1 - LERP) ** (dt * 60)
            current["x"] += (target["x"] - current["x"]) * k
            current["y"] += (target["y"] - current["y"]) * k

            # parallax: layers shift opposite the mouse, scaled by depth
            bg.offset = ft.Offset(-current["x"] * PARALLAX * BG_DEPTH,
                                  -current["y"] * PARALLAX * BG_DEPTH)
            title.offset = ft.Offset(-current["x"] * PARALLAX * FG_DEPTH,
                                     -current["y"] * PARALLAX * FG_DEPTH)

            page.update()
            await asyncio.sleep(1 / 60)

    page.add(
        ft.GestureDetector(
            expand=True,
            on_hover=on_hover,
            on_exit=on_exit,
            content=ft.Stack([bg, page1, page2], expand=True,
                             clip_behavior=ft.ClipBehavior.HARD_EDGE),
        )
    )
    page.run_task(loop)


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)          # newer Flet
    else:
        ft.app(target=main)   # older Flet