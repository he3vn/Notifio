import asyncio
import os
import time
from pathlib import Path

import flet as ft

from .landing.welcome import WelcomePage
from .landing.plugins import PluginsPage
from .landing.done import DonePage

IMAGE = str(Path(__file__).resolve().parents[2] / "Assets" / "landing_bg.jpg")

LERP = 0.15
PARALLAX = 0.03
BG_DEPTH, FG_DEPTH = 0.3, 1.0


class LandingScreen(ft.Container):
    def __init__(self, page: ft.Page, on_finish=None):
        super().__init__(expand=True, bgcolor="#000000")
        self.flet_page = page
        self.on_finish = on_finish
        self.current = "welcome"
        self.selected_plugins = []
        self._running = False

        if not os.path.exists(IMAGE):
            self.content = ft.Text(f"Image not found: {IMAGE}", color="red")
            return

        fit_enum = getattr(ft, "BoxFit", None) or ft.ImageFit
        self._win = {"w": page.width or 1280, "h": page.height or 720}
        self.bg_img = ft.Image(src=IMAGE, fit=fit_enum.COVER,
                               width=self._win["w"], height=self._win["h"],
                               gapless_playback=True)
        self.bg = ft.Container(expand=True, scale=1.12, content=self.bg_img)

        self.pages = {
            "welcome": WelcomePage(on_start=lambda: self.show("plugins")),
            "plugins": PluginsPage(on_back=lambda: self.show("welcome"),
                                   on_continue=self._plugins_done),
            "done": DonePage(on_finish=self._finish),
        }
        for key, pg in self.pages.items():
            pg.root.visible = key == "welcome"

        self.target = {"x": 0.0, "y": 0.0}
        self.cur = {"x": 0.0, "y": 0.0}

        self.content = ft.GestureDetector(
            expand=True,
            on_hover=self._on_pointer,
            on_exit=lambda e: self.target.update(x=0.0, y=0.0),
            content=ft.Stack([self.bg] + [p.root for p in self.pages.values()],
                             expand=True, clip_behavior=ft.ClipBehavior.HARD_EDGE),
        )

    def show(self, name: str):
        self.current = name
        for key, pg in self.pages.items():
            pg.root.visible = key == name
        try:
            self.flet_page.update()
        except Exception:
            pass

    def _plugins_done(self, selected):
        self.selected_plugins = selected
        self.show("done")

    def _finish(self):
        if self.on_finish:
            self.on_finish(list(self.selected_plugins))

    def _on_pointer(self, e):
        try:
            w = self.flet_page.width or 1
            h = self.flet_page.height or 1
            lx = getattr(e, "local_x", None)
            ly = getattr(e, "local_y", None)
            if lx is None:
                pos = getattr(e, "local_position", None)
                if pos is None:
                    return
                lx, ly = getattr(pos, "x", 0), getattr(pos, "y", 0)
            self.target["x"] = max(-1.0, min(1.0, lx / w * 2 - 1))
            self.target["y"] = max(-1.0, min(1.0, ly / h * 2 - 1))
        except Exception:
            pass

    def did_mount(self):
        if not hasattr(self, "pages"):
            return
        self._running = True
        self.flet_page.run_task(self._loop)

    def will_unmount(self):
        self._running = False

    async def _loop(self):
        last = time.perf_counter()
        while self._running:
            now = time.perf_counter()
            dt, last = now - last, now
            try:
                w, h = self.flet_page.width, self.flet_page.height
                if w and h and (w != self._win["w"] or h != self._win["h"]):
                    self._win.update(w=w, h=h)
                    self.bg_img.width, self.bg_img.height = w, h
                k = 1 - (1 - LERP) ** (dt * 60)
                self.cur["x"] += (self.target["x"] - self.cur["x"]) * k
                self.cur["y"] += (self.target["y"] - self.cur["y"]) * k
                self.bg.offset = ft.Offset(-self.cur["x"] * PARALLAX * BG_DEPTH,
                                           -self.cur["y"] * PARALLAX * BG_DEPTH)
                fg = self.pages[self.current].fg
                fg.offset = ft.Offset(-self.cur["x"] * PARALLAX * FG_DEPTH,
                                      -self.cur["y"] * PARALLAX * FG_DEPTH)
                self.bg.update()
                fg.update()
            except Exception:
                pass
            await asyncio.sleep(1 / 60)