import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def build():
    print(f"==> Building Notifio for {sys.platform}...")
    sep = ";" if sys.platform == "win32" else ":"
    
    if sys.platform == "darwin":
        icon_path = ROOT / "Assets" / "icon.icns"
    elif sys.platform == "win32":
        icon_path = ROOT / "Assets" / "icon.ico"
    else:
        icon_path = ROOT / "Assets" / "icon.png"

    cmd = [
        sys.executable, "-c", "from flet.cli import main; import sys; sys.exit(main())",
        "pack",
        str(ROOT / "main.py"),
        "-n", "Notifio",
        "-i", str(icon_path),
        "--add-data", f"Assets{sep}Assets",
        "--add-data", f"UI{sep}UI",
        "-y"
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        print("Build failed!")
        sys.exit(res.returncode)

    dist_dir = ROOT / "dist"

    if sys.platform == "darwin":
        app_path = dist_dir / "Notifio.app"
        zip_path = dist_dir / "Notifio-macOS.zip"
        if app_path.exists():
            print("==> Archiving Notifio.app to Notifio-macOS.zip...")
            if zip_path.exists():
                zip_path.unlink()
            subprocess.run(["zip", "-r", "-y", "Notifio-macOS.zip", "Notifio.app"], cwd=dist_dir)
            print(f"==> Created: {zip_path}")

    elif sys.platform == "win32":
        exe_path = dist_dir / "Notifio.exe"
        zip_path = dist_dir / "Notifio-Windows.zip"
        if exe_path.exists():
            import zipfile
            print("==> Archiving Notifio.exe to Notifio-Windows.zip...")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(exe_path, arcname="Notifio.exe")
            print(f"==> Created: {zip_path}")

    else:
        bin_path = dist_dir / "Notifio"
        tar_path = dist_dir / "Notifio-Linux.tar.gz"
        if bin_path.exists():
            print("==> Archiving Notifio binary to Notifio-Linux.tar.gz...")
            subprocess.run(["tar", "-czf", "Notifio-Linux.tar.gz", "Notifio"], cwd=dist_dir)
            print(f"==> Created: {tar_path}")

    print("==> Build & Packaging completed successfully!")

if __name__ == "__main__":
    build()
