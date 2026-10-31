import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


EXTRA_HIDDEN = [
    "certifi",
    "rumps",
    "PIL",
    "curl_cffi",
    "curl_cffi.requests",
    "cffi",
    "_cffi_backend",
    "xml.etree.ElementTree",
    "html",
    "subprocess",
    "urllib.request",
    "urllib.error",
]


def discover_modules(folder: Path, base: Path) -> list[str]:
    
    mods = []
    if not folder.exists():
        return mods
    for py in sorted(folder.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        rel = py.relative_to(base).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            mods.append(".".join(parts))
    return mods


def flet_supports(flag: str) -> bool:
    """Check whether the installed `flet pack` understands a given option."""
    try:
        res = subprocess.run(
            [sys.executable, "-c",
             "from flet.cli import main; import sys; sys.exit(main())", "pack", "--help"],
            capture_output=True, text=True, cwd=ROOT,
        )
        return flag in (res.stdout + res.stderr)
    except Exception:
        return False


def build():
    if sys.platform != "darwin":
        print("Error: Notifio build is macOS only.")
        sys.exit(1)

    print("==> Building Notifio for macOS...")

    main_py = ROOT / "main.py"
    if not main_py.exists():
        print("Error: main.py not found.")
        sys.exit(1)

    icon_path = ROOT / "Assets" / "icon.icns"
    icon_args = []
    if icon_path.exists():
        icon_args = ["-i", str(icon_path)]
    else:
        print(f"Warning: {icon_path} not found, building without a custom icon.")

    backend_dir = ROOT / "Backend"
    ui_dir = ROOT / "UI"

    hidden = []
    hidden += discover_modules(backend_dir, backend_dir)  
    hidden += discover_modules(ui_dir, ROOT)             
    hidden += EXTRA_HIDDEN
    hidden = list(dict.fromkeys(hidden))  # dedupe, keep order

    print(f"==> Bundling {len(hidden)} hidden imports")
    hidden_args = [a for h in hidden for a in ("--hidden-import", h)]

    extra_args = []
    # Make sure curl_cffi's compiled library is collected (needed for Rumble).
    if flet_supports("--pyinstaller-build-args"):
        extra_args += ["--pyinstaller-build-args=--collect-all=curl_cffi"]
    else:
        print("Note: this flet version has no --pyinstaller-build-args; "
              "relying on hidden imports for curl_cffi.")

    cmd = [
        sys.executable, "-c", "from flet.cli import main; import sys; sys.exit(main())",
        "pack",
        str(main_py),
        "-n", "Notifio",
        *icon_args,
        "--add-data", "Assets:Assets",
        "--add-data", "UI:UI",
        "--add-data", "Backend:Backend",
        *hidden_args,
        *extra_args,
        "-y",
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        print("Build failed!")
        sys.exit(res.returncode)

    dist_dir = ROOT / "dist"
    app_path = dist_dir / "Notifio.app"
    zip_path = dist_dir / "Notifio-macOS.zip"

    if not app_path.exists():
        print("Build finished but dist/Notifio.app was not created.")
        sys.exit(1)

    print("==> Archiving Notifio.app to Notifio-macOS.zip...")
    if zip_path.exists():
        zip_path.unlink()
    subprocess.run(
        ["zip", "-9", "-r", "-y", "Notifio-macOS.zip", "Notifio.app"],
        cwd=dist_dir, check=True,
    )
    print(f"==> Created: {zip_path}")
    print("==> Build & Packaging completed successfully!")
    print("Tip: open dist/Notifio.app and test Twitch, YouTube, Rumble and the menu bar icon.")


if __name__ == "__main__":
    build()