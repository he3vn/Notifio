import subprocess,sys

def _esc(text):
    return str(text).replace("\\", "\\\\").replace('"', '\\"')

def send(title,body="",url=None):
    try:
        if sys.platform == "darwin":
            script = f'display notification "{_esc(body)}" with title "{_esc(title)}"'
            subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        elif sys.platform.startswith("linux"):
            subprocess.run(["notify-send", str(title), str(body)], check=False, timeout=5)
    except Exception:
        pass

        