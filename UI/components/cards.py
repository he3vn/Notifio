#Thumbnail time after i will do downloads etc
import flet as ft
import downloader  # downloads patch
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


def _download_ui(item, on_download, on_choose):
    """Download icon + quality chevron (title row) and progress row. (None, None) if not downloadable."""
    link = item.get("link") or ""
    if not (on_download and link and downloader.can_download(item)):
        return None, None
    ACC, OK, BAD = "#5e6ad2", "#3fb950", "#ef6b6b"
    btn = ft.IconButton(icon=ft.Icons.DOWNLOAD_ROUNDED, icon_size=18, icon_color=S,
                        width=32, height=32, tooltip="Download")
    more = ft.IconButton(icon=ft.Icons.ARROW_DROP_DOWN, icon_size=18, icon_color=S,
                         width=22, height=32, tooltip="Choose quality",
                         on_click=lambda e, it=item: on_choose(it) if on_choose else None)
    bar = ft.ProgressBar(value=0, bar_height=4, color=ACC, bgcolor="#2a2c31",
                         border_radius=2, expand=True)
    info = ft.Text("", size=11, color=S, font_family="Inter-Medium")
    progress = ft.Container(
        visible=False, padding=ft.Padding(4, 0, 4, 4),
        content=ft.Row([bar, info], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def refresh():
        j = downloader.job(link)
        st = j["state"] if j else "idle"
        progress.visible = st != "idle"
        bar.visible = st in downloader.ACTIVE or st == "done"
        if st in downloader.ACTIVE:
            btn.icon, btn.icon_color, btn.tooltip = ft.Icons.DOWNLOAD_ROUNDED, ACC, "Downloading..."
            bar.value = None if st in ("queued", "processing") else j["pct"]
        elif st == "done":
            btn.icon, btn.icon_color, btn.tooltip = ft.Icons.CHECK_CIRCLE_ROUNDED, OK, "Show in folder"
            bar.value = 1
        elif st == "error":
            btn.icon, btn.icon_color, btn.tooltip = ft.Icons.ERROR_OUTLINE, BAD, "Failed. Click to retry"
        else:
            btn.icon, btn.icon_color, btn.tooltip = ft.Icons.DOWNLOAD_ROUNDED, S, "Download"
        info.value = downloader.describe(j) if j else ""
        info.color = BAD if st == "error" else S
        for c in (btn, progress):
            try:
                c.update()
            except Exception:
                pass

    def click(e):
        j = downloader.job(link)
        st = j["state"] if j else "idle"
        if st == "done":
            downloader.reveal(link)
        elif st not in downloader.ACTIVE:
            on_download(item)

    btn.on_click = click
    downloader.watch(link, refresh)
    refresh()
    return ft.Row([btn, more], spacing=0, tight=True), progress


def _card(item, on_delete, on_download=None, on_choose=None):
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
    dl_controls, progress = _download_ui(item, on_download, on_choose)
    body = ft.Container(
        url=item.get("link") or None,
        content=ft.Column(spacing=10, tight=True,
                          horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=[
            media,
            ft.Container(height=38, padding=ft.Padding(4, 0, 4, 0), content=ft.Row(
                [ft.Text(item.get("title", ""), size=14, color=H, font_family="Inter-SemiBold",
                         max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True)]
                + ([dl_controls] if dl_controls else []),
                spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)),
            ft.Container(padding=ft.Padding(4, 0, 4, 2), content=ft.Text(
                meta, size=12, color=S, font_family="Inter-Medium",
                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
            *([progress] if progress else []),
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


def card_grid(items, on_delete, on_download=None, on_choose=None):

    return ft.ResponsiveRow([_card(i, on_delete, on_download, on_choose) for i in items],
                            spacing=GAP, run_spacing=GAP)