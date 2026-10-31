from datetime import datetime
import flet as ft
from pathlib import Path
import notifications
from dexerto.feeds import FEEDS, ago
from .plugins import TOP, BOTTOM
from youtube import feeds as yt
from twitch import feeds as tw
from rumble import feeds as rb

LOGOS = Path(__file__).resolve().parents[2] / "Assets" / "logos"
FILES = dict(TOP + BOTTOM)
AVAILABLE = set(FEEDS) | {"Youtube", "Twitch","Rumble"}
KIND_LABEL = {"video": "Video", "short": "Short", "live": "LIVE", "upcoming": "Upcoming"}
SELECTED_BG = "#2b2d31"
HOVER_BG = "#1c1d21"
H, S, V = "#f7f8f8", "#8a8f98", "#5e6ad2"
MAX_SHOWN = 50

class HomeScreen(ft.Container):
    def __init__(self, name="", on_settings=None, plugins=None):
        super().__init__(bgcolor="#08090a", expand=True)
        self.name = name
        self.on_settings = on_settings
        self.on_refresh = None
        self.on_plugins_changed = None
        self.plugins = list(plugins or [])
        self.selected = None
        self.item_boxes = {}
        self.last_status = ""
        self.adding = False
        self.side_col = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=30,
        )
        sidebar = ft.Container(
            width=220,
            bgcolor="#141516",
            padding=ft.Padding(16, 40, 16, 16),
            content=self.side_col,
        )
        self._rebuild_sidebar()
        self.title = ft.Text("Notifications", size=22, color=H, font_family="Inter-SemiBold", weight=ft.FontWeight.W_600)
        self.subtitle = ft.Text(f"Welcome back, {name}" if name else "", size=13, color=S)
        self.status = ft.Text("", size=11, color=S)
        self.yt_input = ft.TextField(
            hint_text="@handle or channel URL", dense=True, width=320,
            text_style=ft.TextStyle(size=13, color=H), on_submit=self._add_channel,
        )
        self.yt_msg = ft.Text("", size=12, color=S)
        self.tw_input = ft.TextField(
            hint_text="channel name or twitch.tv URL", dense=True, width=320,
            text_style=ft.TextStyle(size=13, color=H), on_submit=self._add_twitch,
        )
        self.tw_msg = ft.Text("", size=12, color=S)
        self.rb_input=ft.TextField(
            hint_text="channel name or rumble URL",dense=True,width=320,
            text_style=ft.TextStyle(size=13,color=H),on_submit=self._add_rumble,
        )
        self.rb_msg=ft.Text("",size=12,color=S)
        self.body = ft.Column(expand=True, spacing=8, scroll=ft.ScrollMode.AUTO)
        main_area = ft.Stack(expand=True, controls=[
            ft.Container(
                expand=True,
                padding=ft.Padding(32, 40, 32, 24),
                content=ft.Column(expand=True, spacing=0, controls=[
                    self.title,
                    self.subtitle,
                    ft.Container(height=4),
                    self.status,
                    ft.Container(height=12),
                    self.body,
                ]),
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE, icon_color=S, icon_size=20,
                tooltip="Clear all notifications", on_click=self._clear, right=96, top=16,
            ),
            ft.IconButton(
                icon=ft.Icons.REFRESH, icon_color=S, icon_size=20,
                tooltip="Check now", on_click=self._manual_refresh, right=56, top=16,
            ),
            ft.IconButton(
                icon=ft.Icons.SETTINGS_OUTLINED, icon_color=S, icon_size=20,
                tooltip="Redo setup", on_click=self._open_settings, right=16, top=16,
            ),
        ])
        self.content = ft.Row(expand=True, spacing=0, controls=[sidebar, main_area])
        self._render()

    def _rebuild_sidebar(self):
        self.item_boxes = {}
        items = [self._item(n) for n in self.plugins]
        self.side_col.controls = [
            ft.Text("Plugins", size=22, color=H, font_family="Inter-SemiBold", weight=ft.FontWeight.W_600),
            ft.Container(height=8),
            *items,
            ft.IconButton(
                icon=ft.Icons.ADD, icon_color=S, icon_size=20,
                tooltip="Add plugin", on_click=self._add_plugin,
            ),
        ]
        for n, box in self.item_boxes.items():
            box.bgcolor = SELECTED_BG if n == self.selected else None

    def _item(self, name):
        path = LOGOS / FILES.get(name, "")
        if path.is_file():
            logo = ft.Image(src=str(path), width=28, height=28, fit=ft.BoxFit.CONTAIN)
        else:
            logo = ft.Container(
                width=28, height=28, alignment=ft.Alignment(0, 0),
                content=ft.Text(name[0], size=18, color=S),
            )
        remove = ft.IconButton(
            icon=ft.Icons.CLOSE, icon_size=14, icon_color=S,
            width=28, height=28, tooltip="Remove plugin", opacity=0,
            on_click=lambda e: self._remove_plugin(name),
        )
        box = ft.Container(
            width=188,
            padding=ft.Padding(8, 2, 4, 2), border_radius=8,
            on_click=lambda e: self._select(name),
            on_hover=lambda e: self._hover(name, e, remove),
            content=ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                logo,
                ft.Text(name, size=13, color=H, font_family="Inter-Medium", expand=True),
                remove,
            ]),
        )
        self.item_boxes[name] = box
        return box

    def _select(self, name):
        self.selected = None if self.selected == name else name
        for n, box in self.item_boxes.items():
            box.bgcolor = SELECTED_BG if n == self.selected else None
        self._render()
        try: self.update()
        except Exception: pass

    def _hover(self, name, e, remove):
        entering = e.data in (True, "true")
        remove.opacity = 1 if entering else 0
        if name != self.selected:
            e.control.bgcolor = HOVER_BG if entering else None
        e.control.update()

    def _open_dialog(self, dlg):
        try:
            self.page.show_dialog(dlg)
        except AttributeError:
            self.page.open(dlg)

    def _close_dialog(self, dlg):
        try:
            self.page.pop_dialog()
        except AttributeError:
            self.page.close(dlg)

    def _add_plugin(self, e):
        all_plugins = TOP + BOTTOM
        available = [n for n, _ in all_plugins if n not in self.plugins]
        if not available:
            dlg = ft.AlertDialog(
                title=ft.Text("Add plugins"),
                content=ft.Text("You've already added every available plugin."),
                actions=[ft.TextButton("Close", on_click=lambda ev: self._close_dialog(dlg))],
            )
            self._open_dialog(dlg)
            return
        checks = {}
        for n in available:
            label = n if n in AVAILABLE else f"{n} (coming soon)"
            checks[n] = ft.Checkbox(label=label, value=False)
        def confirm(ev):
            chosen = [n for n, cb in checks.items() if cb.value]
            self._close_dialog(dlg)
            if chosen:
                self._apply_plugins(chosen)
        dlg = ft.AlertDialog(
            title=ft.Text("Add plugins"),
            content=ft.Column(list(checks.values()), tight=True, spacing=4),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: self._close_dialog(dlg)),
                ft.TextButton("Add", on_click=confirm),
            ],
        )
        self._open_dialog(dlg)

    def _apply_plugins(self, chosen):
        self.plugins = self.plugins + chosen
        self._rebuild_sidebar()
        try: self.update()
        except Exception: pass
        if self.on_plugins_changed:
            self.on_plugins_changed(list(self.plugins))

    def _remove_plugin(self, name):
        self.plugins = [p for p in self.plugins if p != name]
        if self.selected == name:
            self.selected = None
        self._rebuild_sidebar()
        self._render()
        try: self.update()
        except Exception: pass
        if self.on_plugins_changed:
            self.on_plugins_changed(list(self.plugins))

    def _render(self):
        self.title.value = self.selected or "Notifications"
        if not self.selected:
            self.status.value = ""
            self.body.controls = [ft.Text("Select a plugin to view the notifications", size=13, color=S)]
            return
        if self.selected == "Youtube":
            self._render_youtube()
            return
        if self.selected == "Twitch":
            self._render_twitch()
            return
        if self.selected=="Rumble":
            self._render_rumble()
            return
        self.status.value=self.last_status

        self.status.value = self.last_status
        items = [i for i in notifications.load() if i.get("plugin") == self.selected][:MAX_SHOWN]
        if items:
            self.body.controls = [self._row(i) for i in items]
        elif self.selected not in AVAILABLE:
            self.body.controls = [ft.Text("This source isn't available yet.", size=13, color=S)]
        else:
            self.body.controls = [ft.Text("No notifications yet.", size=13, color=S)]

    def _row(self, item):
        delete = ft.IconButton(
            icon=ft.Icons.CLOSE, icon_size=16, icon_color=S,
            tooltip="Remove", opacity=0,
            on_click=lambda e: self._delete(item),
        )
        def hover(e):
            delete.opacity = 1 if e.data in (True, "true") else 0
            try: delete.update()
            except Exception: pass
        return ft.Container(
            padding=ft.Padding(14, 4, 6, 4), border_radius=8, bgcolor="#141516",
            on_hover=hover,
            content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Container(
                    url=item["link"], expand=True,
                    padding=ft.Padding(0, 6, 0, 6),
                    content=ft.Column(spacing=2, controls=[
                        ft.Text(item["title"], size=13, color=H, font_family="Inter-Medium"),
                        ft.Text(
                            f'{item["source"]} · {KIND_LABEL[item["kind"]]} · {ago(item["ts"])}'
                            if item.get("kind") in KIND_LABEL
                            else f'{item["source"]} · {ago(item["ts"])}',
                            size=11, color=S,
                        ),
                    ]),
                ),
                delete,
            ]),
        )

    def _delete(self, item):
        notifications.remove(item["link"])
        self._render()
        try: self.update()
        except Exception: pass

    def _clear(self, e):
        notifications.clear_all()
        self._render()
        try: self.update()
        except Exception: pass

    def on_poll(self, added, failed, fresh=None):
        now = datetime.now().strftime("%H:%M")
        self.last_status = f"Couldn't refresh at {now}" if failed else f"Last checked {now}"
        if self.selected:
            self._render()
        try: self.update()
        except Exception: pass

    def _manual_refresh(self, e):
        if self.on_refresh:
            self.last_status = "Checking..."
            self._render()
            try: self.update()
            except Exception: pass
            self.on_refresh()

    def _open_settings(self, e):
        if self.on_settings:
            self.on_settings()

    

    def _render_youtube(self):
        self.status.value = self.last_status
        chips = [
            ft.Container(
                padding=ft.Padding(10, 2, 2, 2), border_radius=14, bgcolor="#141516",
                content=ft.Row(tight=True, spacing=4, controls=[
                    ft.Text(ch["name"], size=12, color=H, font_family="Inter-Medium"),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=12, icon_color=S, width=24, height=24,
                                  on_click=lambda e, ch=ch: self._remove_channel(ch)),
                ]),
            )
            for ch in yt.load_channels()
        ]
        prefs = yt.load_prefs()
        def pref_box(label, kind):
            return ft.Checkbox(
                label=label, value=kind in prefs,
                on_change=lambda e, k=kind: self._on_yt_pref(k, e),
            )
        items = [i for i in notifications.load() if i.get("plugin") == "Youtube"][:MAX_SHOWN]
        self.body.controls = [
            ft.Row([self.yt_input, ft.Button("Add", on_click=self._add_channel, height=36)], spacing=8),
            self.yt_msg,
            ft.Row(chips, wrap=True, spacing=6, run_spacing=6),
            ft.Text("Notify me for:", size=12, color=S),
            ft.Row([pref_box("Videos", "video"), pref_box("Shorts", "short"), pref_box("Lives", "live")], spacing=4),
            ft.Container(height=8),
            *([self._row(i) for i in items]
              or [ft.Text("No videos yet. Add a channel above.", size=13, color=S)]),
        ]

    def _add_channel(self, e):
        text = (self.yt_input.value or "").strip()
        if not text or self.adding:
            return
        self.adding = True
        self.yt_msg.value = "Looking up channel..."
        self.yt_input.disabled = True
        try: self.update()
        except Exception: pass
        def work():
            try:
                ch = yt.add_channel(text)
                self.yt_msg.value, self.yt_input.value = f"Added {ch['name']}", ""
            except Exception as ex:
                self.yt_msg.value = f"Couldn't add channel: {ex}"
            self.adding = False
            self.yt_input.disabled = False
            self._render()
            try: self.update()
            except Exception: pass
        self.page.run_thread(work)

    def _on_yt_pref(self, kind, e):
        raw = str(e.data).lower() if e.data is not None else ""
        if raw in ("true", "false"):
            on = raw == "true"
        else:
            on = bool(e.control.value)
        types = [t for t in yt.load_prefs() if t != kind]
        if on:
            types.append(kind)
        yt.save_prefs(types)

    def _remove_channel(self, ch):
        yt.remove_channel(ch["id"])
        self._render()
        try: self.update()
        except Exception: pass

   
    def _render_twitch(self):
        self.status.value = self.last_status
        chips = [
            ft.Container(
                padding=ft.Padding(10, 2, 2, 2), border_radius=14, bgcolor="#141516",
                content=ft.Row(tight=True, spacing=4, controls=[
                    ft.Text(ch["name"], size=12, color=H, font_family="Inter-Medium"),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=12, icon_color=S, width=24, height=24,
                                  on_click=lambda e, ch=ch: self._remove_twitch(ch)),
                ]),
            )
            for ch in tw.load_channels()
        ]
        items = [i for i in notifications.load() if i.get("plugin") == "Twitch"][:MAX_SHOWN]
        self.body.controls = [
            ft.Row([self.tw_input, ft.Button("Add", on_click=self._add_twitch, height=36)], spacing=8),
            self.tw_msg,
            ft.Row(chips, wrap=True, spacing=6, run_spacing=6),
            ft.Container(height=8),
            *([self._row(i) for i in items]
              or [ft.Text("No streams yet. Add a channel above.", size=13, color=S)]),
        ]

    def _add_twitch(self, e):
        text = (self.tw_input.value or "").strip()
        if not text or self.adding:
            return
        self.adding = True
        self.tw_msg.value = "Looking up channel..."
        self.tw_input.disabled = True
        try: self.update()
        except Exception: pass
        def work():
            try:
                ch = tw.add_channel(text)
                self.tw_msg.value, self.tw_input.value = f"Added {ch['name']}", ""
                if self.on_refresh:
                    self.on_refresh()  # check right away so an already-live channel pings now
            except Exception as ex:
                self.tw_msg.value = f"Couldn't add channel: {ex}"
            self.adding = False
            self.tw_input.disabled = False
            self._render()
            try: self.update()
            except Exception: pass
        self.page.run_thread(work)

    def _remove_twitch(self, ch):
        tw.remove_channel(ch["id"])
        self._render()
        try: self.update()
        except Exception: pass

    def _render_rumble(self):
        self.status.value = self.last_status
        chips = [
            ft.Container(
                padding=ft.Padding(10, 2, 2, 2), border_radius=14, bgcolor="#141516",
                content=ft.Row(tight=True, spacing=4, controls=[
                    ft.Text(ch["name"], size=12, color=H, font_family="Inter-Medium"),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=12, icon_color=S, width=24, height=24,
                                  on_click=lambda e, ch=ch: self._remove_rumble(ch)),
                ]),
            )
            for ch in rb.load_channels()
        ]
        items = [i for i in notifications.load() if i.get("plugin") == "Rumble"][:MAX_SHOWN]
        self.body.controls = [
            ft.Row([self.rb_input, ft.Button("Add", on_click=self._add_rumble, height=36)], spacing=8),
            self.rb_msg,
            ft.Row(chips, wrap=True, spacing=6, run_spacing=6),
            ft.Container(height=8),
            *([self._row(i) for i in items]
              or [ft.Text("No videos yet. Add a channel above.", size=13, color=S)]),
        ]

    def _add_rumble(self,e):
        text=(self.rb_input.value or "").strip()
        if not text or self.adding: return
        self.adding=True
        self.rb_msg.value="Looking up channel..."
        self.rb_input.disabled=True
        try: self.update()
        except Exception: pass
        def work():
            try:
                ch=rb.add_channel(text)
                self.rb_msg.value,self.rb_input.value=f"Added {ch['name']}", ""
            except Exception as ex:
                self.rb_msg.value=f"Couldn't add channel: {ex}"
            self.adding=False
            self.rb_input.disabled=False
            self._render()
            try: self.update()
            except Exception: pass
        self.page.run_thread(work)


    def _remove_rumble(self,ch):
        rb.remove_channel(ch["id"])
        self._render()
        try:self.update()
        except Exception:pass

