"""In-app macOS toast notifications.

Why this exists: macOS only lets *signed app bundles* post real Notification
Center banners. Running from VS Code (plain python) there is no bundle, so
rumps/pyobjc/etc. fail, and the osascript fallback is attributed to Script
Editor (clicking it opens Script Editor). So the tray process draws its own
small floating banner instead. It needs no bundle, no permission prompt, and
a click goes exactly where we tell it (the video / stream / article).

Everything here must run on the main thread (it is driven by rumps timers).
"""
import time
import traceback
from pathlib import Path

import objc
from AppKit import (
    NSColor,
    NSCursor,
    NSFont,
    NSImage,
    NSImageView,
    NSMakeRect,
    NSPanel,
    NSScreen,
    NSTextField,
    NSView,
)

WIDTH, HEIGHT = 360, 78
MARGIN, GAP = 14, 10
LIFETIME = 7.0
MAX_VISIBLE = 4

# Raw AppKit constants (stable values; avoids name differences between pyobjc versions)
_STYLE = 0 | (1 << 7)                      # borderless + non-activating panel
_BUFFERED = 2
_LEVEL_STATUS = 25                         # NSStatusWindowLevel
_BEHAVIOR = (1 << 0) | (1 << 4) | (1 << 8)  # all spaces, stationary, full-screen aux
_SCALE_FIT = 3                             # NSImageScaleProportionallyUpOrDown


class _ToastView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(_ToastView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.on_click = None
        self.on_dismiss = None
        return self

    def acceptsFirstMouse_(self, event):
        return True

    def hitTest_(self, point):
        # Swallow clicks on the labels/icon so the whole banner is one button.
        hit = objc.super(_ToastView, self).hitTest_(point)
        return self if hit is not None else None

    def mouseDown_(self, event):
        cb = self.on_click
        if cb:
            try:
                cb()
            except Exception:
                traceback.print_exc()

    def rightMouseDown_(self, event):
        cb = self.on_dismiss
        if cb:
            cb()

    def resetCursorRects(self):
        self.addCursorRect_cursor_(self.bounds(), NSCursor.pointingHandCursor())


def _label(text, rect, size, bold, alpha, lines):
    f = NSTextField.alloc().initWithFrame_(rect)
    f.setStringValue_(str(text))
    f.setBezeled_(False)
    f.setDrawsBackground_(False)
    f.setEditable_(False)
    f.setSelectable_(False)
    f.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1.0, alpha))
    f.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    cell = f.cell()
    if lines > 1:
        cell.setWraps_(True)
        cell.setLineBreakMode_(0)  # word wrap
        cell.setTruncatesLastVisibleLine_(True)
    else:
        cell.setWraps_(False)
        cell.setLineBreakMode_(4)  # truncate tail
    f.setMaximumNumberOfLines_(lines)
    return f


class ToastManager:
    def __init__(self, icon_path=None):
        self.icon_path = icon_path
        self._icon = None
        self._toasts = []  # newest first: dicts with panel + expires

    def _icon_image(self):
        if self._icon is None and self.icon_path and Path(self.icon_path).is_file():
            self._icon = NSImage.alloc().initWithContentsOfFile_(self.icon_path)
        return self._icon

    def show(self, title, body, on_click):
        """on_click() is called when the banner is clicked."""
        toast = {}
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, WIDTH, HEIGHT), _STYLE, _BUFFERED, False)
        panel.setLevel_(_LEVEL_STATUS)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setFloatingPanel_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setCollectionBehavior_(_BEHAVIOR)

        view = _ToastView.alloc().initWithFrame_(NSMakeRect(0, 0, WIDTH, HEIGHT))
        view.setWantsLayer_(True)
        layer = view.layer()
        layer.setBackgroundColor_(NSColor.colorWithCalibratedWhite_alpha_(0.11, 0.97).CGColor())
        layer.setCornerRadius_(14.0)
        layer.setBorderWidth_(1.0)
        layer.setBorderColor_(NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.14).CGColor())

        image = self._icon_image()
        if image is not None:
            iv = NSImageView.alloc().initWithFrame_(NSMakeRect(14, (HEIGHT - 44) / 2, 44, 44))
            iv.setImage_(image)
            iv.setImageScaling_(_SCALE_FIT)
            view.addSubview_(iv)

        text_x, text_w = 70, WIDTH - 70 - 14
        view.addSubview_(_label(title, NSMakeRect(text_x, HEIGHT - 32, text_w, 18), 13, True, 1.0, 1))
        view.addSubview_(_label(body, NSMakeRect(text_x, 10, text_w, 34), 12, False, 0.72, 2))

        def clicked():
            self._remove(toast)
            on_click()

        view.on_click = clicked
        view.on_dismiss = lambda: self._remove(toast)
        panel.setContentView_(view)

        toast.update(panel=panel, expires=time.monotonic() + LIFETIME)
        self._toasts.insert(0, toast)
        while len(self._toasts) > MAX_VISIBLE:
            self._remove(self._toasts[-1])
        self._layout()
        panel.orderFrontRegardless()

    def tick(self):
        now = time.monotonic()
        for toast in [t for t in self._toasts if t["expires"] <= now]:
            self._remove(toast)

    def _remove(self, toast):
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)
        try:
            toast["panel"].orderOut_(None)
            toast["panel"].close()
        except Exception:
            traceback.print_exc()
        self._layout()

    def _layout(self):
        screens = NSScreen.screens()
        screen = screens[0] if screens else NSScreen.mainScreen()  # [0] = the one with the menu bar
        frame = screen.visibleFrame()
        x = frame.origin.x + frame.size.width - WIDTH - MARGIN
        top = frame.origin.y + frame.size.height - MARGIN
        for i, toast in enumerate(self._toasts):
            y = top - HEIGHT - i * (HEIGHT + GAP)
            toast["panel"].setFrame_display_(NSMakeRect(x, y, WIDTH, HEIGHT), True)
