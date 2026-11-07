import json
import os
import socket
import sys
import threading
import traceback
from storage import get_data_dir, read_json, write_json
 
WINDOWS = sys.platform.startswith("win")
PORTS = {"main": 48731, "tray": 48732}
MISSED_FILE = get_data_dir() / "missed.json"
_LOCK = threading.Lock()
 
 
def _address(target):
    if WINDOWS:
        return ("127.0.0.1", PORTS[target])
    name = "notifio" if target == "main" else f"notifio-{target}"
    return f"/tmp/{name}-{os.getuid()}.sock"
 
 
def _new_socket():
    family = socket.AF_INET if WINDOWS else socket.AF_UNIX
    return socket.socket(family, socket.SOCK_STREAM)
 
 
def get_missed():
    d = read_json(MISSED_FILE, {})
    try:
        return max(0, int(d.get("count", 0)))
    except Exception:
        return 0
 
 
def add_missed(n):
    with _LOCK:
        write_json(MISSED_FILE, {"count": get_missed() + n})
 
 
def clear_missed():
    with _LOCK:
        write_json(MISSED_FILE, {"count": 0})
 
 
def send(cmd, arg=None, timeout=2.0, target="main"):
    line = cmd if arg is None else f"{cmd} {json.dumps(arg)}"
    s = _new_socket()
    s.settimeout(timeout)
    try:
        s.connect(_address(target))
        s.sendall((line + "\n").encode())
        return s.recv(16).strip() == b"ok"
    except OSError:
        return False
    finally:
        s.close()
 
 
class Server:
    def __init__(self, handlers, target="main"):
        self.handlers = handlers
        self.address = _address(target)
        if not WINDOWS:
            try:
                os.unlink(self.address)
            except FileNotFoundError:
                pass
        self.sock = _new_socket()
        self.sock.bind(self.address)
        if not WINDOWS:
            os.chmod(self.address, 0o600)
        self.sock.listen(4)
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn,_=self.sock.accept()
            except OSError: return
            try:
                conn.settimeout(2)
                line=conn.makefile().readline().strip()
                name, _, raw = line.partition(" ")
                fn=self.handlers.get(name)
                if fn:
                    if raw:
                        fn(json.loads(raw))
                    else:
                        fn()
                    conn.sendall(b"ok\n")
                else:
                    conn.sendall(b"no\n")
            except Exception:
                traceback.print_exc()
            finally:
                conn.close()

    def close(self):
        try:
            self.sock.close()
            if not WINDOWS:
                os.unlink(self.address)
        except Exception:
            pass