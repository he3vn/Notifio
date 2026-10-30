import os, socket, threading,traceback
from storage import get_data_dir, read_json,write_json

SOCK=f"/tmp/notifio-{os.getuid()}.sock"
MISSED_FILE=get_data_dir() /"missed.json"
_LOCK=threading.Lock()

def get_missed():
    d=read_json(MISSED_FILE,{})
    try:
        return max(0,int(d.get("count",0)))
    except Exception: return 0

def add_missed(n):
    with _LOCK:
        write_json(MISSED_FILE,{"count":get_missed()+n})

def clear_missed():
    with _LOCK:
        write_json(MISSED_FILE, {"count": 0})

def send(cmd,timeout=2.0):
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(SOCK)
        s.sendall((cmd+"\n").encode())
        return s.recv(16).strip() ==b"ok"
    except OSError: return False
    finally: s.close()

class Server:
    def __init__(self,handlers):
        self.handlers=handlers
        try: os.unlink(SOCK)
        except FileNotFoundError: pass
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.bind(SOCK)
        os.chmod(SOCK, 0o600)
        self.sock.listen(4)
        threading.Thread(target=self._serve,daemon=True).start()

    def _serve(self):
        while True:
            try: conn,_=self.sock.accept()
            except OSError: return
            try:
                conn.settimeout(2)
                cmd=conn.makefile().readline().strip()
                fn=self.handlers.get(cmd)
                if fn:
                    fn()
                    conn.sendall(b"ok\n")
                else:
                    conn.sendall(b"no\n")
            except Exception: traceback.print_exc()
            finally: conn.close()

    def close(self):
        try:
            self.sock.close()
            os.unlink(SOCK)
        except Exception: pass
    