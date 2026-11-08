import asyncio
import colorsys
import subprocess
import sys
import traceback
from datetime import datetime
import flet as ft
from pathlib import Path
import notifications
import app_settings
import sound
from dexerto.feeds import FEEDS, ago
from .cards import card_grid  # thumbnails patch
from storage import save_user,load_user
from .plugins import TOP, BOTTOM
from youtube import feeds as yt
from twitch import feeds as tw
from rumble import feeds as rb
try:
    import flet_video as ftv
except ImportError:
    ftv=None

ASSETS=Path(__file__).resolve().parents[2] /"Assets"
LOGOS= ASSETS/"logos"
BRAND_LOGO= ASSETS/"Ferdium_1024x1024x32-recolored.png"
BG_IMAGE=ASSETS/"landing_bg.jpg"
BG_VIDEO=ASSETS/"wallpaper.mp4"

FILES= dict(TOP+BOTTOM)
AVAILAIBLE=set(FEEDS) | {"Youtube", "Twitch", "Rumble"}
KIND_LABEL={"video":"Video","short":"Short","live":"LIVE","upcoming":"Upcoming"}
H, S = "#f7f8f8", "#8a8f98"
MAX_SHOWN=50
PANEL_BG="#D908090a"
PILL_BG = "#f7f8fb"
PILL_TEXT = "#0b0b0f"
PILL_SELECTED = "#dfe3ee"
BAR_H = 48
PAD = 6
BRAND_W = 40
ITEM_H = 36
ICON_W = 40
GAP = 2
BTN=ft.ButtonStyle(bgcolor="#f7f8fb",color="#0b0b0f",shape=ft.RoundedRectangleBorder(radius=19),padding=ft.Padding(22,0,22,0),text_style=ft.TextStyle(font_family="Inter-Medium",size=13,weight=ft.FontWeight.W_500))

def _anim(ms=260):
    return ft.Animation(ms,ft.AnimationCurve.EASE_OUT)

def _name_w(name):
    return max(64,int(len(name)*8+34))

def _tint(hue,amt):
     r,g,b=(int(c*255) for c in colorsys.hls_to_rgb(hue/360,0.85,1))
     return  f"#{int(amt*255):02x}{r:02x}{g:02x}{b:02x}"




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
        self.nav_hover=False
        self.nav_items={}
        bg = self._pref("bg_video", "")
        self._bg_path = bg if ftv and bg and Path(bg).is_file() else ""

        self.title=ft.Text("Notifications",size=22,color=H,font_family="Inter-SemiBold",weight=ft.FontWeight.W_600)
        self.subtitle=ft.Text(f"Welcome back, {name}"if name else "",size=13,color=S)
        self.status=ft.Text("",size=11,color=S)
        self.remove_btn=ft.TextButton(
            "Remove plugin",visible=False,
            on_click=self._remove_selected,
            style=ft.ButtonStyle(color="#ef6b6b"),

        )
        self.yt_input=ft.TextField(
            hint_text="@handle or channel URL",dense=True,width=320,
            text_style=ft.TextStyle(size=13,color=H),
            on_submit=self._add_channel,
        )
        self.yt_msg=ft.Text("",size=12,color=S)
        self.tw_input=ft.TextField(
            hint_text="channel name or twitch.tv URL",dense=True,width=320,
            text_style=ft.TextStyle(size=13,color=H),
            on_submit=self._add_twitch,
        )
        self.tw_msg=ft.Text("",size=12,color=S)
        self.rb_input=ft.TextField(
            hint_text="channel name or rumble URL",dense=True,width=320,
            text_style=ft.TextStyle(size=13,color=H),
            on_submit=self._add_rumble,
        )
        self.rb_msg=ft.Text("",size=12,color=S)
        self.body=ft.Column(expand=True,spacing=8,scroll=ft.ScrollMode.AUTO)

        panel=ft.Container(
            expand=True,
            padding=ft.Padding(16,14,16,16),
            content=ft.Container(
                expand=True,bgcolor=PANEL_BG,border_radius=20,
                padding=ft.Padding(28,24,28,20),
                content=ft.Column(expand=True, spacing=0, controls=[
                    ft.Row(
                        [self.title, ft.Container(expand=True), self.remove_btn],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.subtitle,
                    ft.Container(height=4),
                    self.status,
                    ft.Container(height=12),
                    self.body,
                ]),
            ),
        )

        self.nav_row=ft.Row(spacing=GAP, tight=True,vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.nav_pill=ft.Container(
            height=BAR_H,border_radius=BAR_H /2,bgcolor=PILL_BG,
            padding=ft.Padding(PAD,0,PAD,0),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=_anim(260),
            on_hover=self._nav_hover,
            shadow=[ft.BoxShadow(blur_radius=14,color="#33000000",offset=ft.Offset(0, 4))],
            content=self.nav_row
        )
        self._rebuild_nav()

        def action(icon,tip,handler):
            return ft.IconButton(icon=icon,icon_color="#ffffff",icon_size=20,tooltip=tip,on_click=handler,width=40,height=40)
        actions=ft.Container(
            height=BAR_H,border_radius=BAR_H / 2,bgcolor="#000000",
            padding=ft.Padding(PAD,0,PAD,0),
            shadow=[ft.BoxShadow(blur_radius=14,color="#33000000",offset=ft.Offset(0, 4))],
            content=ft.Row(
                spacing=0,tight=True,vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    action(ft.Icons.ADD,"Add plugin",self._add_plugin),
                    action(ft.Icons.DELETE_OUTLINE,"Clear all notifications",self._clear),
                    action(ft.Icons.REFRESH,"Check now",self._manual_refresh),
                    action(ft.Icons.SETTINGS_OUTLINED,"Settings",self._toggle_settings),
                    ],
            )
        )

        top_bar=ft.Container(
            padding=ft.Padding(16,16,16,0),
            content=ft.Row(
                [self.nav_pill,ft.Container(expand=True),actions],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,

            ),
        )

        self.wall=ft.Container(left=0,right=0,top=0,bottom=0,content=self._bg())
        self.veil=ft.Container(left=0,right=0,top=0,bottom=0,bgcolor=_tint(self._pref("bg_hue",200),self._pref("bg_tint",0)))
        self.tabcol=ft.Column(spacing=4)
        self.pane=ft.Container(expand=True,height=280,padding=ft.Padding(20,18,18,18))
        self.settings_box=ft.Container(
            visible=False,right=16,top=BAR_H+24,width=480,height=280,
            bgcolor="#000000",border_radius=18,clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.Border.all(1,"#23252a"),
            shadow=[ft.BoxShadow(blur_radius=24,color="#66000000",offset=ft.Offset(0,8))],
            content=ft.Row([ft.Container(content=self.tabcol,width=130,height=280,padding=10,bgcolor="#0e0f11"),self.pane],spacing=0),
        )
        self.content=ft.Stack(expand=True,controls=[self.wall,self.veil,ft.Container(left=0,right=0,top=0,bottom=0,content=ft.Column(expand=True,spacing=0,controls=[top_bar, panel])),self.settings_box])
        self._tab("Setup")
        self._render()
        


    def _safe_update(self):
        try:
            self.update()
        except Exception:
            pass

    def _open_dialog(self,dlg):
        try:
            self.page.show_dialog(dlg)
        except AttributeError:
            self.page.open(dlg)

    def _close_dialog(self,dlg):
        try:
            self.page.pop_dialog()
        except AttributeError:
            self.page.close(dlg)

    def _pref(self,k,d):
        return (load_user()or {}).get(k,d)

    def _bg(self):
        if ftv and self._bg_path and Path(self._bg_path).is_file():
            return ftv.Video(playlist=[ftv.VideoMedia(self._bg_path)],playlist_mode=ftv.PlaylistMode.LOOP,autoplay=True,muted=True,fit=ft.BoxFit.COVER,expand=True)
        return self._image_bg()

    def _image_bg(self):
        return ft.Image(src=str(BG_IMAGE),fit=ft.BoxFit.COVER,expand=True,gapless_playback=True) if BG_IMAGE.is_file() else ft.Container()

    def _set_bg(self,p):
        save_user({"bg_video":p})
        self._bg_path = p if ftv and p and Path(p).is_file() else ""
        self.wall.content=self._bg()
        self._tab("Background")

    def _drop_media_player(self):
        """Kick the mpv player out of the page.

        The Flet client aborts (SIGABRT inside Mpv) when it tears down while a
        video player is still running, so before the window hides or the app
        quits we always swap the background video for the static image.
        """
        try:
            if ftv and isinstance(self.wall.content, ftv.Video):
                self.wall.content = self._image_bg()
                self._safe_update()
        except Exception:
            traceback.print_exc()

    async def pause_media(self):
        """Freeze playback while the window is hidden, keeping the player alive.

        Tearing an mpv player down while it plays is what crashes flet's client
        on macOS (SIGSEGV inside Mpv), so pause is as far as we go here.
        """
        try:
            if ftv and isinstance(self.wall.content, ftv.Video):
                await self.wall.content.pause()
        except Exception:
            traceback.print_exc()

    async def play_media(self):
        try:
            if ftv and isinstance(self.wall.content, ftv.Video):
                await self.wall.content.play()
        except Exception:
            traceback.print_exc()

    def drop_media(self):
        """Remove the video widget so its mpv player is released.

        Only call this from the quit path, after a pause has had time to settle
        and never right before another window operation.
        """
        try:
            if ftv and isinstance(self.wall.content, ftv.Video):
                self.wall.content = self._image_bg()
                self._safe_update()
        except Exception:
            traceback.print_exc()

    def _pick_fallback(self,uti,prompt):
        if sys.platform!="darwin":
            return ""
        r=subprocess.run(["osascript","-e",f'POSIX path of (choose file of type {{"{uti}"}} with prompt "{prompt}")'],capture_output=True,text=True)
        return r.stdout.strip()

    async def _pick(self,e):
        try:
            f=await ft.FilePicker().pick_files(file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=["mp4"],allow_multiple=False)
            p=f[0].path if f else None
        except Exception:
            p=await asyncio.to_thread(self._pick_fallback,"public.mpeg-4","Select MP4")
        if p:
            self._set_bg(p)

    async def _pick_sound(self,e):
        try:
            f=await ft.FilePicker().pick_files(file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=["mp3"],allow_multiple=False)
            p=f[0].path if f else None
        except Exception:
            p=await asyncio.to_thread(self._pick_fallback,"public.mp3","Select MP3")
        if p:
            stored=app_settings.store_sound(p)
            if stored:
                app_settings.set_value("sound_file",stored)
                self._tab("Sound")

    def _reset_sound(self,e):
        app_settings.set_value("sound_file","")
        self._tab("Sound")

    def _tab(self,k):
        panes={"Setup":self._p_setup,"Background":self._p_bg,"Theme":self._p_theme,"Sound":self._p_sound}
        self.tabcol.controls=[ft.Container(content=ft.Text(t,size=13,color=H if t==k else S,font_family="Inter-Medium"),padding=ft.Padding(12,9,12,9),border_radius=10,bgcolor="#1c1d20" if t==k else None,on_click=lambda e,t=t:self._tab(t)) for t in panes]
        self.pane.content=panes[k]()
        self._safe_update()

    def _p_setup(self):
        return ft.Column([ft.Button("Redo setup",on_click=self._redo,height=38,style=BTN)])

    def _p_bg(self):
        p=self._pref("bg_video","") or str(BG_VIDEO)
        self.bg_msg=ft.Text("Run: pip install flet-video" if p and not ftv else Path(p).name or "Default",size=12,color=S)
        return ft.Column([ft.Button("Choose MP4",on_click=self._pick,height=38,style=BTN),ft.Button("Use default",on_click=lambda e:self._set_bg(""),height=38,style=BTN),self.bg_msg],spacing=12)

    def _p_sound(self):
        def toggle(e):
            app_settings.set_value("sound",bool(e.control.value))
        name=Path(app_settings.get("sound_file") or "").name or "Default sound"
        switch=ft.Switch(label="Play sound",value=bool(app_settings.get("sound")),on_change=toggle)
        return ft.Column([
            switch,
            ft.Button("Choose MP3",on_click=self._pick_sound,height=38,style=BTN),
            ft.Button("Use default",on_click=self._reset_sound,height=38,style=BTN),
            ft.Button("Test sound",on_click=lambda e:sound.alert(force=True),height=38,style=BTN),
            ft.Text(name,size=12,color=S),
        ],spacing=10)
    
    def _p_theme(self):
        def apply(e):
            self.veil.bgcolor=_tint(hue.value,amt.value)
            self.veil.update()
        def save(e):
            save_user({"bg_hue":hue.value,"bg_tint":amt.value})
        hue=ft.Slider(min=0,max=360,value=self._pref("bg_hue",200),on_change=apply,on_change_end=save,thumb_color="#ffffff",active_color="#00000000",inactive_color="#00000000")
        amt=ft.Slider(min=0,max=0.8,value=self._pref("bg_tint",0),on_change=apply,on_change_end=save,thumb_color="#ffffff",active_color="#8a8f98",inactive_color="#26282c")
        rainbow=ft.Container(left=12,right=12,top=20,height=8,border_radius=4,gradient=ft.LinearGradient(colors=[_tint(x,1) for x in range(0,361,60)]))
        return ft.Column([ft.Text("Color",size=12,color=S),ft.Stack([rainbow,hue]),ft.Text("Strength",size=12,color=S),amt],spacing=6)


    def _brand(self):
        if BRAND_LOGO.is_file():
            img=ft.Image(src=str(BRAND_LOGO),width=28,height=28,border_radius=8,fit=ft.BoxFit.CONTAIN)
        else:
            img=ft.Icon(ft.Icons.NOTIFICATIONS_NONE,size=22,color=PILL_TEXT)
        return ft.Container(
                        width=BRAND_W,height=ITEM_H,border_radius=ITEM_H /2,bgcolor=PILL_TEXT,
            alignment=ft.Alignment(0,0),content=img,
            tooltip="Home",on_click=self._go_home,
        )

    def _nav_item(self,name):
        path=LOGOS/FILES.get(name,"")
        if path.is_file():
            logo=ft.Image(src=str(path),width=24,height=24,fit=ft.BoxFit.CONTAIN)
        else:
            logo = ft.Text(name[0], size=16, color=PILL_TEXT, weight=ft.FontWeight.W_700)
        logo_layer=ft.Container(
            left=0,right=0,top=0,bottom=0,alignment=ft.Alignment(0,0),
            content=logo,opacity=1,animate_opacity=_anim(200),
        )
        text_layer=ft.Container(
            left=0,right=0,top=0,bottom=0,
            alignment=ft.Alignment(0,0),
            content=ft.Text(name,size=13,color=PILL_TEXT,font_family="Inter-Medium",no_wrap=True),
            opacity=0,animate_opacity=_anim(200),
        )
        box=ft.Container(
            width=ICON_W,height=ITEM_H,border_radius=ITEM_H/2,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=_anim(260),
            on_click=lambda e, n=name: self._select(n),
            content=ft.Stack([logo_layer, text_layer]),
        )
        self.nav_items[name]={"box":box,"logo":logo_layer,"text":text_layer}
        return box

    def _rebuild_nav(self):
        self.nav_items={}
        boxes = [self._nav_item(n) for n in self.plugins]
        self.nav_row.controls = [self._brand(), *boxes]
        self._layout_nav()

    def _layout_nav(self):
        total=PAD*2 +BRAND_W
        for name in self.plugins:
            it=self.nav_items.get(name)
            if not it:
                continue
            w=_name_w(name) if self.nav_hover else ICON_W
            it["box"].width = w
            it["box"].bgcolor = PILL_SELECTED if name == self.selected else None
            it["logo"].opacity = 0 if self.nav_hover else 1
            it["text"].opacity = 1 if self.nav_hover else 0
            total += w +GAP
        self.nav_pill.width=total

    def _nav_hover(self,e):
        on=str(e.data).lower() =="true"
        if on == self.nav_hover:
            return
        self.nav_hover=on
        self._layout_nav()
        try:
            self.nav_pill.update()
        except Exception:
            pass

    def _view_changed(self):
        self.settings_box.visible=False
        self._layout_nav()
        self._render()
        self._safe_update()

    def _select(self,name):
        self.selected=None if self.selected == name else name
        self._view_changed()

    def _go_home(self,e=None):
        self.selected=None
        self._view_changed()

    def _toggle_settings(self,e):
        self.settings_box.visible=not self.settings_box.visible
        self._safe_update()

    def _redo(self,e):
        self.settings_box.visible=False
        self._safe_update()
        if self.on_settings:
            self.on_settings()

    def _add_plugin(self,e):
        self.settings_box.visible=False
        self._safe_update()
        available=[n for n, _ in TOP + BOTTOM if n not in self.plugins]
        if not available:
            dlg=ft.AlertDialog(
                title=ft.Text("Add plugins"),
                content=ft.Text("You've already added every available plugin."),
                actions=[ft.TextButton("Close", on_click=lambda ev: self._close_dialog(dlg))],
            )
            self._open_dialog(dlg)
            return
        checks= {}
        for n in available:
            label= n if n in AVAILAIBLE else f"{n} (coming soon)"
            checks[n]=ft.Checkbox(label=label,value=False)

        def confirm(ev):
            chosen=[n for n,cb in checks.items() if cb.value]
            self._close_dialog(dlg)
            if chosen:
                self._apply_plugins(chosen)

        dlg = ft.AlertDialog(
            title=ft.Text("Add plugins"),
            content=ft.Column(list(checks.values()), tight=True, spacing=4),
            actions=[
                ft.TextButton("Cancel",on_click=lambda ev: self._close_dialog(dlg)),
                ft.TextButton("Add",on_click=confirm),
            ],
        )
        self._open_dialog(dlg)

    def _apply_plugins(self,chosen):
        self.plugins=self.plugins+chosen
        self.selected=chosen[0]
        self._rebuild_nav()
        self._render()
        self._safe_update()
        if self.on_plugins_changed:
            self.on_plugins_changed(list(self.plugins))

    def _remove_plugin(self,name):
        self.plugins=[p for p in self.plugins if p != name]
        if self.selected == name:
            self.selected=None
        self._rebuild_nav()
        self._render()
        self._safe_update()
        if self.on_plugins_changed:
            self.on_plugins_changed(list(self.plugins))

    def _remove_selected(self,e):
        if self.selected:
            self._remove_plugin(self.selected)

    def _render(self):
        self.title.value=self.selected or "Notifications"
        self.remove_btn.visible=bool(self.selected)
        if not self.selected:
            self.status.value=""
            msg = ("Select a plugin to view the notifications" if self.plugins else "No plugins yet. Press + to add one.")
            self.body.controls = [ft.Text(msg, size=13, color=S)]
            return
        if self.selected=="Youtube":
            self._render_youtube()
            return
        if self.selected=="Twitch":
            self._render_twitch()
            return
        if self.selected=="Rumble":
            self._render_rumble()
            return
        self.status.value=self.last_status
        items=[i for i in notifications.load() if i.get("plugin")== self.selected][:MAX_SHOWN]
        if items:
            self.body.controls = self._cards(items, "")
        elif self.selected not in AVAILAIBLE:
            self.body.controls=[ft.Text("This source isnt availaible yet.",size=13,color=S)]
        else:
            self.body.controls = [ft.Text("No notifications yet.", size=13, color=S)]


    def _row(self,item):
        delete=ft.IconButton(
            icon=ft.Icons.CLOSE,icon_size=16,icon_color=S,
            tooltip="Remove",opacity=0,
            on_click=lambda e: self._delete(item),
        )

        def hover(e):
            delete.opacity=1 if e.data in(True,"true") else 0
            try:
                delete.update()
            except Exception:
                pass

        return ft.Container(
            padding=ft.Padding(14,4,6,4),border_radius=8,bgcolor="#141516",
            on_hover=hover,
            content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Container(
                    url=item["link"],expand=True,
                    padding=ft.Padding(0,6,0,6),
                    content=ft.Column(spacing=2,controls=[
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

    def _cards(self,items,empty):  # thumbnails patch
        if not items:
            return [ft.Text(empty,size=13,color=S)] if empty else []
        return [card_grid(items,self._delete)]

    def _delete(self,item):
        notifications.remove(item["link"])
        self._render()
        self._safe_update()

    def _clear(self,e):
        self.settings_box.visible=False
        notifications.clear_all()
        self._render()
        self._safe_update()

    def on_poll(self,added,failed,fresh=None):
        now=datetime.now().strftime("%H:%M")
        self.last_status = f"Couldn't refresh at {now}" if failed else f"Last checked {now}"
        if self.selected:
            self._render()
        self._safe_update()

    def _manual_refresh(self,e):
        self.settings_box.visible=False
        if self.on_refresh:
            self.last_status="Checking..."
            self._render()
            self._safe_update()
            self.on_refresh()
        else:
            self._safe_update()

    def _render_youtube(self):
        self.status.value=self.last_status
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
        prefs= yt.load_prefs()

        def pref_box(label,kind):
            return ft.Checkbox(
                label=label,value=kind in prefs,
                on_change=lambda e,k=kind: self._on_yt_pref(k,e),
            )

        items=[i for i in notifications.load() if i.get("plugin") == "Youtube"][:MAX_SHOWN]
        self.body.controls=[
            ft.Row([self.yt_input, ft.Button("Add", on_click=self._add_channel, height=36)], spacing=8),
            self.yt_msg,
            ft.Row(chips,wrap=True,spacing=6,run_spacing=6),
            ft.Text("Notify me for:",size=12,color=S),
            ft.Row([pref_box("Videos", "video"), pref_box("Shorts", "short"), pref_box("Lives", "live")], spacing=4),
            ft.Container(height=8),
            *self._cards(items, "No videos yet. Add a channel above."),
        ]

    def _add_channel(self,e):
        text=(self.yt_input.value or"").strip()
        if not text or self.adding:
            return
        self.adding=True
        self.yt_msg.value="Looking up channel..."
        self.yt_input.disabled=True
        self._safe_update()

        def work():
            try:
                ch=yt.add_channel(text)
                self.yt_msg.value,self.yt_input.value=f"Added {ch['name']}",""
            except Exception as ex:
                self.yt_msg.value=f"Couldn't add channel: {ex}"
            self.adding=False
            self.yt_input.disabled=False
            self._render()
            self._safe_update()

        self.page.run_thread(work)

    def _on_yt_pref(self,kind,e):
        raw=str(e.data).lower() if e.data is not None else ""
        if raw in("true","false"):
            on= raw=="true"
        else:
            on=bool(e.control.value)
        types=[t for t in yt.load_prefs() if t != kind]
        if on:
            types.append(kind)
        yt.save_prefs(types)

    def _remove_channel(self,ch):
        yt.remove_channel(ch["id"])
        self._render()
        self._safe_update()

    def _render_twitch(self):
        self.status.value=self.last_status
        chips=[
            ft.Container(
                padding=ft.Padding(10,2,2,2),border_radius=14,bgcolor="#141516",
                content=ft.Row(tight=True,spacing=4,controls=[
                    ft.Text(ch["name"], size=12, color=H, font_family="Inter-Medium"),
                    ft.IconButton(icon=ft.Icons.CLOSE,icon_size=12,icon_color=S,width=24,height=24,on_click=lambda e,ch=ch: self._remove_twitch(ch)),
                ]),
            )
            for ch in tw.load_channels()
        ]
        items=[i for i in notifications.load() if i.get("plugin")=="Twitch"][:MAX_SHOWN]
        self.body.controls = [
            ft.Row([self.tw_input, ft.Button("Add", on_click=self._add_twitch, height=36)], spacing=8),
            self.tw_msg,
            ft.Row(chips,wrap=True,spacing=6,run_spacing=6),
            ft.Container(height=8),
            *self._cards(items, "No streams yet.Add a channel above."),
        ]

    def _add_twitch(self,e):
        text=(self.tw_input.value or"").strip()
        if not text or self.adding:
            return
        self.adding=True
        self.tw_msg.value="Looking up channel..."
        self.tw_input.disabled=True
        self._safe_update()

        def work():
            try:
                ch=tw.add_channel(text)
                self.tw_msg.value,self.tw_input.value=f"Added {ch['name']}", ""
                if self.on_refresh:
                    self.on_refresh()
            except Exception as ex:
                self.tw_msg.value=f"Couldnt add channel: {ex}"
            self.adding=False
            self.tw_input.disabled=False
            self._render()
            self._safe_update()

        self.page.run_thread(work)

    def _remove_twitch(self,ch):
        tw.remove_channel(ch["id"])
        self._render()
        self._safe_update()

    def _render_rumble(self):
        self.status.value=self.last_status
        chips=[
            ft.Container(
                padding=ft.Padding(10,2,2,2),border_radius=14,bgcolor="#141516",
                content=ft.Row(tight=True, spacing=4, controls=[
                    ft.Text(ch["name"], size=12, color=H, font_family="Inter-Medium"),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=12, icon_color=S, width=24, height=24,
                                  on_click=lambda e, ch=ch: self._remove_rumble(ch)),
                ]),
            )
            for ch in rb.load_channels()

        ]
        items=[i for i in notifications.load() if i.get("plugin")=="Rumble"][:MAX_SHOWN]
        self.body.controls=[
            ft.Row([self.rb_input, ft.Button("Add", on_click=self._add_rumble, height=36)], spacing=8),
            self.rb_msg,
            ft.Row(chips,wrap=True,spacing=6,run_spacing=6),
            ft.Container(height=8),
            *self._cards(items, "No videos yet. Add a channel above."),
        ]

    def _add_rumble(self,e):
        text=(self.rb_input.value or "").strip()
        if not text or self.adding:
            return
        self.adding=True
        self.rb_msg.value="Looking up channel..."
        self.rb_input.disabled=True
        self._safe_update()

        def work():
            try:
                ch=rb.add_channel(text)
                self.rb_msg.value,self.rb_input.value=f"Added {ch['name']}",""
            except Exception as ex:
                self.rb_msg.value=f"Couldnt add channel: {ex}"
            self.adding=False
            self.rb_input.disabled=False
            self._render()
            self._safe_update()

        self.page.run_thread(work)

    def _remove_rumble(self,ch):
        rb.remove_channel(ch["id"])
        self._render()
        self._safe_update()