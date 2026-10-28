import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parent

UI_DIR = ROOT_DIR / "UI"
BACKEND_DIR = ROOT_DIR / "Backend"
ASSETS_DIR = ROOT_DIR / "Assets"

for d in (UI_DIR, BACKEND_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

import flet as ft


import ssl, urllib.request, xml.etree.ElementTree, email.utils, certifi  # noqa: F401

from ui import main

if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=str(ASSETS_DIR))
    else:
        ft.app(target=main, assets_dir=str(ASSETS_DIR))