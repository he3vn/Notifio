import subprocess
import sys


def _esc(text):
    t = str(text).replace("\\", "\\\\").replace('"', '\\"')
    return t.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def send(title, body="", url=None):
    try:
        if sys.platform == "darwin":
            script = f'''
            try
                tell application "Notifio" to display notification "{_esc(body)}" with title "{_esc(title)}" sound name "default"
            on error
                tell application "System Events" to display notification "{_esc(body)}" with title "{_esc(title)}" sound name "default"
            end try
            '''
            subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception:
        pass
