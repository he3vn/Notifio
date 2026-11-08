#Thumbnail time after i will do downloads etc
import flet as ft
from dexerto.feeds import ago, fmt_count

H, S = "#f7f8f8", "#8a8f98"
CARD_BG, CARD_BG_HOVER = "#141516", "#1b1c1f"
PLACEHOLDER_BG = "#1c1d20"
THUMB_H = 200
GAP = 16

BADGES = {
    "live": ("LIVE", "#e5484d", True),
    "short": ("SHORT", "#5e6ad2", False),
    "upcoming": ("UPCOMING", "#3a3d44", False),
}


def _anim(ms=160):
    return ft.Animation(ms, ft.AnimationCurve.EASE_OUT)


def thumb_url(item):

    t = item.get("thumb")
    if t:
        return t
    link = item.get("link", "")
    if "youtube.com/watch?v=" in link:
        vid = link.split("v=")[-1].split("&")[0]
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    if item.get("plugin") == "Twitch" and item.get("channel_id"):
        return f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{item['channel_id']}-640x360.jpg"
    return ""


def views_text(item):
    v = item.get("views")
    if v is None:
        return ""
    text = fmt_count(v)
    if not text:
        return ""
    live = item.get("kind") == "live" and item.get("plugin") in ("Twitch", "Rumble")  # watching patch
    return f"{text} {'watching' if live else 'views'}"


def _placeholder():
    return ft.Container(
        height=THUMB_H, width=float("inf"), bgcolor=PLACEHOLDER_BG,
        alignment=ft.Alignment(0, 0),
        content=ft.Icon(ft.Icons.IMAGE_OUTLINED, size=34, color="#3a3d44"),
    )


def _badge(text, bg, dot):
    parts = []
    if dot:
        parts.append(ft.Container(width=6, height=6, border_radius=3, bgcolor="#ffffff"))
    parts.append(ft.Text(text, size=10, color="#ffffff", font_family="Inter-SemiBold",
                         weight=ft.FontWeight.W_600))
    return ft.Container(
        padding=ft.Padding(8, 3, 8, 3), border_radius=6, bgcolor=bg,
        content=ft.Row(parts, spacing=5, tight=True,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )


def _card(item, on_delete):
    url = thumb_url(item)
    image = _placeholder()
    if url:
        image = ft.Image(src=url, width=float("inf"), height=THUMB_H, fit=ft.BoxFit.COVER,
                         gapless_playback=True, error_content=_placeholder())
    media = ft.Container(height=THUMB_H, border_radius=12, bgcolor=PLACEHOLDER_BG,
                         clip_behavior=ft.ClipBehavior.HARD_EDGE, content=image)

    badge = BADGES.get(item.get("kind"))
    if badge:
        media = ft.Stack([media, ft.Container(left=8, top=8, content=_badge(*badge))])

    meta = " · ".join(p for p in (item.get("source", ""), views_text(item), ago(item.get("ts"))) if p)
    body = ft.Container(
        url=item.get("link") or None,
        content=ft.Column(spacing=10, tight=True,
                          horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=[
            media,
            ft.Container(height=38, padding=ft.Padding(4, 0, 4, 0), content=ft.Text(
                item.get("title", ""), size=14, color=H, font_family="Inter-SemiBold",
                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)),
            ft.Container(padding=ft.Padding(4, 0, 4, 2), content=ft.Text(
                meta, size=12, color=S, font_family="Inter-Medium",
                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
        ]),
    )

    delete = ft.Container(
        right=10, top=10, opacity=0, animate_opacity=_anim(140),
        content=ft.IconButton(
            icon=ft.Icons.CLOSE, icon_size=14, icon_color="#ffffff", width=28, height=28,
            tooltip="Remove", style=ft.ButtonStyle(bgcolor="#a6000000"),
            on_click=lambda e, it=item: on_delete(it)),
    )

    card = ft.Container(
        col=4, padding=8, border_radius=16, bgcolor=CARD_BG,
        scale=1.0, animate=_anim(160), animate_scale=_anim(160),
        content=ft.Stack([body, delete]),
    )

    def hover(e):
        on = str(e.data).lower() == "true"
        card.scale = 1.02 if on else 1.0
        card.bgcolor = CARD_BG_HOVER if on else CARD_BG
        delete.opacity = 1 if on else 0
        try:
            card.update()
        except Exception:
            pass

    card.on_hover = hover
    return card


def card_grid(items, on_delete):

    return ft.ResponsiveRow([_card(i, on_delete) for i in items],
                            spacing=GAP, run_spacing=GAP)