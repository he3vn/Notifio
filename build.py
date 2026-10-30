import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def build():
    if sys.platform != "darwin":
        print("Error: Notifio build is macOS only.")
        sys.exit(1)

    print("==> Building Notifio for macOS...")
    icon_path = ROOT / "Assets" / "icon.icns"

    hidden = ["dexerto.feeds", "youtube.feeds", "notifications", "notifier", "poller",
              "storage", "certifi","twitch.feeds"]
    hidden_args = [a for h in hidden for a in ("--hidden-import", h)]

    cmd = [
        sys.executable, "-c", "from flet.cli import main; import sys; sys.exit(main())",
        "pack",
        str(ROOT / "main.py"),
        "-n", "Notifio",
        "-i", str(icon_path),
        "--add-data", "Assets:Assets",
        "--add-data", "UI:UI",
        "--add-data", "Backend:Backend",
        *hidden_args,
        "-y"
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        print("Build failed!")
        sys.exit(res.returncode)

    dist_dir = ROOT / "dist"
    app_path = dist_dir / "Notifio.app"
    zip_path = dist_dir / "Notifio-macOS.zip"

    if app_path.exists():
        print("==> Archiving Notifio.app to Notifio-macOS.zip...")
        if zip_path.exists():
            zip_path.unlink()
        subprocess.run(["zip", "-9", "-r", "-y", "Notifio-macOS.zip", "Notifio.app"], cwd=dist_dir)
        print(f"==> Created: {zip_path}")

    print("==> Build & Packaging completed successfully!")

if __name__ == "__main__":
    build()