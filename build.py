import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAC = sys.platform == "darwin"
WINDOWS = sys.platform.startswith("win")

COMMON_HIDDEN = [
    "certifi",
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
    "webbrowser",
]

MAC_HIDDEN = ["AppKit", "Foundation", "UserNotifications", "objc"]
WINDOWS_HIDDEN = ["winotify", "pystray", "pystray._win32", "ctypes", "winsound"]
MAC_BUNDLE_ID = "com.notifio.app"


def tune_mac_bundle(app_path: Path) -> None:
    """Make the .app bundle provider-ready for native notifications.

    UNUserNotificationCenter (the only API macOS still delivers with) needs a
    CFBundleIdentifier plus NSUserNotificationsUsageDescription in Info.plist,
    and the bundle must be re-signed after the plist changes.
    """
    import plistlib

    plist = app_path / "Contents" / "Info.plist"
    try:
        data = plistlib.loads(plist.read_bytes()) if plist.exists() else {}
        data["CFBundleIdentifier"] = MAC_BUNDLE_ID
        data["CFBundleName"] = "Notifio"
        data["CFBundleDisplayName"] = "Notifio"
        # Menu-bar app: the Python host has no UI of its own (the Flet client
        # owns the window), so keep it out of the Dock/Cmd+Tab entirely.
        data["LSUIElement"] = True
        data["NSUserNotificationsUsageDescription"] = (
            "Notifio shows pop-ups when creators you follow upload or go live."
        )
        plist.write_bytes(plistlib.dumps(data))
    except Exception as exc:
        print(f"Warning: could not update {plist}: {exc}")
        return
    res = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_path)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print("Warning: ad-hoc re-sign of Notifio.app failed:\n" + res.stderr)
    else:
        print("==> Info.plist tuned for notifications, app re-signed")


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
    try:
        res = subprocess.run(
            [sys.executable, "-c",
             "from flet.cli import main; import sys; sys.exit(main())", "pack", "--help"],
            capture_output=True, text=True, cwd=ROOT,
        )
        return flag in (res.stdout + res.stderr)
    except Exception:
        return False


def package_mac(dist_dir: Path) -> Path:
    app_path = dist_dir / "Notifio.app"
    zip_path = dist_dir / "Notifio-macOS.zip"
    if not app_path.exists():
        print("Build finished but dist/Notifio.app was not created.")
        sys.exit(1)
    tune_mac_bundle(app_path)
    if zip_path.exists():
        zip_path.unlink()
    subprocess.run(
        ["zip", "-9", "-r", "-y", "Notifio-macOS.zip", "Notifio.app"],
        cwd=dist_dir, check=True,
    )
    return zip_path


def package_windows(dist_dir: Path) -> Path:
    exe_path = dist_dir / "Notifio.exe"
    folder_path = dist_dir / "Notifio"
    zip_path = dist_dir / "Notifio-Windows.zip"
    if not exe_path.exists() and not folder_path.exists():
        print("Build finished but dist/Notifio.exe was not created.")
        sys.exit(1)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        if exe_path.exists():
            z.write(exe_path, "Notifio.exe")
        else:
            for f in folder_path.rglob("*"):
                if f.is_file():
                    z.write(f, Path("Notifio") / f.relative_to(folder_path))
    return zip_path


def build():
    if not (MAC or WINDOWS):
        print("Error: Notifio builds on macOS and Windows only.")
        sys.exit(1)

    label = "macOS" if MAC else "Windows"
    print(f"==> Building Notifio for {label}...")

    main_py = ROOT / "main.py"
    if not main_py.exists():
        print("Error: main.py not found.")
        sys.exit(1)

    icon_path = ROOT / "Assets" / ("icon.icns" if MAC else "icon.ico")
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
    hidden += COMMON_HIDDEN
    hidden += MAC_HIDDEN if MAC else WINDOWS_HIDDEN
    hidden = list(dict.fromkeys(hidden))

    print(f"==> Bundling {len(hidden)} hidden imports")
    hidden_args = [a for h in hidden for a in ("--hidden-import", h)]

    extra_args = []
    if flet_supports("--pyinstaller-build-args"):
        extra_args += ["--pyinstaller-build-args=--collect-all=curl_cffi"]
    else:
        print("Note: this flet version has no --pyinstaller-build-args; "
              "relying on hidden imports for curl_cffi.")
    if MAC and flet_supports("--bundle-id"):
        extra_args += ["--bundle-id", MAC_BUNDLE_ID]

    sep = os.pathsep
    cmd = [
        sys.executable, "-c", "from flet.cli import main; import sys; sys.exit(main())",
        "pack",
        str(main_py),
        "-n", "Notifio",
        *icon_args,
        "--add-data", f"Assets{sep}Assets",
        "--add-data", f"UI{sep}UI",
        "--add-data", f"Backend{sep}Backend",
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
    print("==> Archiving build...")
    zip_path = package_mac(dist_dir) if MAC else package_windows(dist_dir)
    print(f"==> Created: {zip_path}")
    print("==> Build & Packaging completed successfully!")
    print("Tip: run the build and test Twitch, YouTube, Rumble, notification clicks and the tray icon.")


if __name__ == "__main__":
    build()