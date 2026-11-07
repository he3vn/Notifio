import os
import queue
import subprocess
import sys
import time
import traceback
import uuid
import webbrowser
from pathlib import Path
import control

WINDOWS = sys.platform.startswith("win")


def _icon(names):
    root = Path(os.environ.get("NOTIFIO_ROOT", Path(__file__).resolve().parents[1]))
    for name in names:
        p = root / "Assets" / name
        if p.is_file():
            return str(p)
    return None


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _missed_text(n):
    return "No missed notifications" if n == 0 else f"{n} missed notification{'s' if n != 1 else ''}"


def run(parent_pid):
    """Runs the menu-bar helper.

    It must never crash the app: every platform API call is wrapped, and the
    process only ever exits through os._exit() from its own watchdog, so the
    tray stays up while the app window is hidden and dies when the app quits.
    """
    if WINDOWS:
        _run_windows(parent_pid)
    else:
        _run_mac(parent_pid)


# --------------------------------------------------------------------------
# macOS: NSStatusItem + UNUserNotificationCenter (no rumps, no Script Editor)
# --------------------------------------------------------------------------
def _open(url):
    """Click action for a notification: go to the item's own page."""
    try:
        if url:
            webbrowser.open(url)
        else:
            control.send("open")
    except Exception:
        traceback.print_exc()


def _run_mac(parent_pid):
    from AppKit import (NSApplication, NSApplicationActivationPolicyAccessory,
                        NSImage, NSMenu, NSMenuItem, NSStatusBar,
                        NSVariableStatusItemLength)
    from Foundation import NSTimer, NSObject

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    pending = queue.Queue()          # notifications waiting to be posted
    urls = {}                        # notification id -> click URL
    state = {"post": None, "misses": 0, "last": -1, "alive": True}
    missed_item = None               # set once the menu is built

    # ---- notification posters ----
    def make_un_post():
        try:
            from UserNotifications import (UNAuthorizationOptionAlert,
                                           UNMutableNotificationContent,
                                           UNNotificationRequest,
                                           UNUserNotificationCenter)
            center = UNUserNotificationCenter.currentNotificationCenter()
        except Exception:
            traceback.print_exc()
            return None

        status = {"granted": None}

        class CenterDelegate(NSObject):
            def userNotificationCenter_willPresentNotification_withCompletionHandler_(
                    self, center_, notification, handler):
                try:
                    from UserNotifications import (UNNotificationPresentationOptionBanner,
                                                   UNNotificationPresentationOptionList)
                    handler(int(UNNotificationPresentationOptionList | UNNotificationPresentationOptionBanner))
                except Exception:
                    try:
                        handler(0)
                    except Exception:
                        pass
                return None

            def userNotificationCenter_didReceiveNotificationResponse_withCompletionHandler_(
                    self, center_, response, handler):
                url = ""
                try:
                    ident = response.notification().request().identifier()
                    url = urls.get(ident, "") or ""
                except Exception:
                    traceback.print_exc()
                handler()
                _open(url)
                return None

        try:
            center.setDelegate_(CenterDelegate.alloc().init())
        except Exception:
            traceback.print_exc()

        def auth_handler(granted, error):
            status["granted"] = bool(granted)

        try:
            center.requestAuthorizationWithOptions_completionHandler_(
                UNAuthorizationOptionAlert, auth_handler)
        except Exception:
            traceback.print_exc()

        def post(title, body, url):
            # When macOS says denied (e.g. running as bare python), raise so
            # the chain falls back to the next poster instead of eating toasts.
            if status["granted"] is False:
                raise PermissionError("notification permission denied")
            ident = uuid.uuid4().hex
            urls[ident] = url or ""
            if len(urls) > 200:
                for k in list(urls)[:len(urls) - 200]:
                    urls.pop(k, None)
            content = UNMutableNotificationContent.alloc().init()
            content.setTitle_(str(title or "Notifio"))
            content.setBody_(str(body or ""))
            request = UNNotificationRequest.requestWithIdentifier_content_trigger_(ident, content, None)
            center.addNotificationRequest_withCompletionHandler_(request, None)

        return post

    un_post = make_un_post()

    def post_any(title, body, url=""):
        # Only UNUserNotificationCenter: it is the one macOS still delivers,
        # and it attributes the toast to Notifio. osascript toasts were removed
        # on purpose — macOS attributes them to Script Editor/Terminal and a
        # click opens that editor instead of the item page.
        if un_post is None:
            print("tray: UserNotifications unavailable, notification dropped",
                  file=sys.stderr)
            return
        try:
            un_post(title, body, url)
        except Exception:
            print("tray: notification not posted (permission denied?)",
                  file=sys.stderr)
            traceback.print_exc()

    state["post"] = post_any

    # ---- status item & menu ----
    class TrayActions(NSObject):
        def open_(self, sender):
            if not control.send("open"):
                try:
                    state["post"]("Notifio", "Couldn't reach the app. Try relaunching it.", "")
                except Exception:
                    traceback.print_exc()

        def recheck_(self, sender):
            control.send("recheck")

        def quit_(self, sender):
            try:
                control.send("quit")
            except Exception:
                traceback.print_exc()
            os._exit(0)

        def tick_(self, timer):
            try:
                if not _alive(parent_pid):
                    os._exit(0)
                if control.send("ping", timeout=1.0):
                    state["misses"] = 0
                else:
                    state["misses"] += 1
                    if state["misses"] >= 5:
                        os._exit(0)
                        return
                n = control.get_missed()
                if n != state["last"]:
                    state["last"] = n
                    if missed_item is not None:
                        missed_item.setTitle_(_missed_text(n))
            except Exception:
                traceback.print_exc()

        def drain_(self, timer):
            while True:
                try:
                    item = pending.get_nowait()
                except queue.Empty:
                    return
                try:
                    state["post"](item.get("title") or "Notifio",
                                  item.get("body") or "",
                                  item.get("url") or "")
                except Exception:
                    traceback.print_exc()

    class TrayAppDelegate(NSObject):
        def applicationShouldTerminate_(self, sender):
            return 0  # the tray only exits on its own terms

    actions = TrayActions.alloc().init()
    app.setDelegate_(TrayAppDelegate.alloc().init())

    try:
        server = control.Server({"notify": pending.put}, target="tray")
    except Exception:
        traceback.print_exc()
        server = None

    item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
    button = item.button()
    try:
        path = _icon(("tray.png", "icon.png"))
        img = NSImage.alloc().initWithContentsOfFile_(path) if path else None
        if img is not None:
            img.setSize_((18.0, 18.0))
            button.setImage_(img)
        else:
            button.setTitle_("N")
    except Exception:
        traceback.print_exc()
        button.setTitle_("N")

    menu = NSMenu.alloc().init()
    menu.setAutoenablesItems_(False)

    def add_item(title, action):
        mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
        mi.setTarget_(actions)
        mi.setEnabled_(True)
        menu.addItem_(mi)
        return mi

    add_item("Open Notifio", "open:")
    missed_item = add_item("No missed notifications", "open:")
    add_item("Recheck now", "recheck:")
    menu.addItem_(NSMenuItem.separatorItem())
    add_item("Quit Notifio", "quit:")
    item.setMenu_(menu)

    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(0.2, actions, "drain:", None, True)
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(2.0, actions, "tick:", None, True)
    app.run()
    # Should never be reached; keep the helper alive just in case.
    while True:
        time.sleep(3600)


# --------------------------------------------------------------------------
# Windows: pystray (works as-is with winotify doing the toasts)
# --------------------------------------------------------------------------
def _run_windows(parent_pid):
    import threading
    import pystray
    from PIL import Image

    path = _icon(("tray.ico", "tray.png", "icon.png"))
    image = Image.open(path) if path else Image.new("RGBA", (64, 64), (94, 106, 210, 255))

    pending = queue.Queue()  # unused, kept for protocol parity with macOS

    def open_app(icon=None, item=None):
        control.send("open")

    def recheck(icon=None, item=None):
        control.send("recheck")

    def quit_app(icon=None, item=None):
        control.send("quit")
        icon.stop()

    def missed_label(item):
        return _missed_text(control.get_missed())

    menu = pystray.Menu(
        pystray.MenuItem("Open Notifio", open_app, default=True),
        pystray.MenuItem(missed_label, open_app),
        pystray.MenuItem("Recheck now", recheck),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Notifio", quit_app),
    )
    icon = pystray.Icon("Notifio", image, "Notifio", menu)

    def watch():
        misses = 0
        last = -1
        while True:
            time.sleep(2)
            if not _alive(parent_pid):
                os._exit(0)
            if control.send("ping"):
                misses = 0
            else:
                misses += 1
                if misses >= 5:
                    os._exit(0)
            n = control.get_missed()
            if n != last:
                last = n
                try:
                    icon.update_menu()
                except Exception:
                    pass

    def setup(icon_):
        icon_.visible = True
        threading.Thread(target=watch, daemon=True).start()

    icon.run(setup)
