import os
import sys
from pathlib import Path

# Resolve base directories
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parent

UI_DIR = ROOT_DIR / "UI"
ASSETS_DIR = ROOT_DIR / "Assets"

if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

import flet as ft
from ui import main

if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main, assets_dir=str(ASSETS_DIR))
    else:
        ft.app(target=main, assets_dir=str(ASSETS_DIR))
