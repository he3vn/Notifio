import os
import sys
from pathlib import Path


if getattr(sys,"frozen",False):
    ROOT_DIR=Path(sys._MEIPASS)
else: ROOT_DIR=Path(__file__).resolve().parent

os.environ["NOTIFIO_ROOT"]= str(ROOT_DIR)

UI_DIR=ROOT_DIR/"UI"
BACKEND_DIR=ROOT_DIR/"Backend"
ASSETS_DIR=ROOT_DIR/"Assets"

for d in(UI_DIR,BACKEND_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0,str(d))

if "--tray" in sys.argv:
    import tray
    try:
        pid=int(sys.agrv[sys.agrv.index("--tray")+1])
    except Exception: pid= os.getpid()
    tray.run(pid)
    sys.exit(0)

import control
if control.send("open"):
    sys.exit(0)

import flet as ft
from ui import main

if __name__=="__main__":
    if hasattr(ft,"run"):
        ft.run(main,assets_dir=str(ASSETS_DIR))
    else: ft.app(target=main,assets_dir=str(ASSETS_DIR))