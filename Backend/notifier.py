import subprocess, sys


def _esc(text):
    """Escape text for AppleScript double-quoted strings."""
    t = str(text)
    t = t.replace("\\", "\\\\").replace('"', '\\"')
    # Strip characters that can break osascript (newlines, tabs, control chars)
    t = t.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return t


def send(title, body="", url=None):
    try:
        if sys.platform == "darwin":
            script = f'display notification "{_esc(body)}" with title "{_esc(title)}" sound name "default"'
            subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        elif sys.platform.startswith("linux"):
            subprocess.run(["notify-send", str(title), str(body)], check=False, timeout=5)
    except Exception:
        pass
