import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAC = sys.platform == "darwin"
WINDOWS = sys.platform.startswith("win")
APP_NAME = "Notifio"
APP_VERSION = "1.1.0"
FILE_VERSION = "1.1.0.0"
MAC_ZIP = "Notifio-macOS.zip"
WIN_ZIP = "Notifio-Windows.zip"

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
    "flet_video",
    "yt_dlp",
    "yt_dlp_ejs",
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
        data["CFBundleName"] = APP_NAME
        data["CFBundleDisplayName"] = APP_NAME
        data["CFBundleShortVersionString"] = APP_VERSION
        data["CFBundleVersion"] = APP_VERSION
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
    app_path = dist_dir / f"{APP_NAME}.app"
    zip_path = dist_dir / MAC_ZIP
    if not app_path.exists():
        print("Build finished but dist/Notifio.app was not created.")
        sys.exit(1)
    tune_mac_bundle(app_path)
    if zip_path.exists():
        zip_path.unlink()
    subprocess.run(
        ["zip", "-9", "-r", "-y", MAC_ZIP, APP_NAME + ".app"],
        cwd=dist_dir, check=True,
    )
    return zip_path


def package_windows(dist_dir: Path) -> Path:
    exe_path = dist_dir / f"{APP_NAME}.exe"
    folder_path = dist_dir / APP_NAME
    zip_path = dist_dir / WIN_ZIP
    if not exe_path.exists() and not folder_path.exists():
        print("Build finished but neither dist/Notifio.exe nor dist/Notifio was created.")
        sys.exit(1)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        wrote = False
        # One-dir builds put the exe and every dependency inside dist/Notifio.
        if folder_path.is_dir():
            for f in folder_path.rglob("*"):
                if f.is_file():
                    z.write(f, Path(APP_NAME) / f.relative_to(folder_path))
                    wrote = True
        # One-file builds only produce dist/Notifio.exe.
        if exe_path.is_file() and not (folder_path / exe_path.name).is_file():
            z.write(exe_path, exe_path.name)
            wrote = True
        if not wrote:
            print("Build finished but there was nothing to package.")
            sys.exit(1)
    return zip_path


def target_for_platform():
    if MAC:
        return "macos"
    if WINDOWS:
        return "windows"
    return None


def build(target: str) -> int:
    if target == "macos" and not MAC:
        print("Error: the macOS .app can only be built on macOS.")
        print("Run this on a Mac, or push a v* tag so the release workflow builds it.")
        return 1
    if target == "windows" and not WINDOWS:
        print("Error: PyInstaller cannot cross-compile a Windows .exe from macOS.")
        print("Run `python build.py --windows` on Windows, or push a v* tag so")
        print(".github/workflows/release.yml builds the Windows zip on a Windows runner.")
        return 1

    label = "macOS" if target == "macos" else "Windows"
    print(f"==> Building Notifio for {label}...")

    main_py = ROOT / "main.py"
    if not main_py.exists():
        print("Error: main.py not found.")
        return 1

    icon_path = ROOT / "Assets" / ("icon.icns" if target == "macos" else "icon.ico")
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
    hidden += MAC_HIDDEN if target == "macos" else WINDOWS_HIDDEN
    hidden = list(dict.fromkeys(hidden))

    print(f"==> Bundling {len(hidden)} hidden imports")
    hidden_args = [a for h in hidden for a in ("--hidden-import", h)]

    extra_args = []
    if flet_supports("--pyinstaller-build-args"):
        extra_args += [
            f"--pyinstaller-build-args=--paths={backend_dir}",
            f"--pyinstaller-build-args=--paths={ROOT}",
            "--pyinstaller-build-args=--collect-all=curl_cffi",
        ]
    else:
        print("Note: this flet version has no --pyinstaller-build-args; "
              "relying on hidden imports for curl_cffi.")
    if target == "macos" and flet_supports("--bundle-id"):
        extra_args += ["--bundle-id", MAC_BUNDLE_ID]

    version_args = [
        "--product-name", APP_NAME,
        "--product-version", APP_VERSION,
    ]
    if target == "windows":
        version_args += [
            "--file-version", FILE_VERSION,
            "--company-name", "Notifio",
            "--copyright", "MIT",
        ]

    sep = os.pathsep
    cmd = [
        sys.executable, "-c", "from flet.cli import main; import sys; sys.exit(main())",
        "pack",
        str(main_py),
        "-n", APP_NAME,
        *icon_args,
        *version_args,
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
        return res.returncode

    dist_dir = ROOT / "dist"
    print("==> Archiving build...")
    zip_path = package_mac(dist_dir) if target == "macos" else package_windows(dist_dir)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"==> Created: {zip_path} ({size_mb:.1f} MB)")
    print("==> Build & Packaging completed successfully!")
    print("Tip: run the build and test Twitch, YouTube, Rumble, notification clicks and the tray icon.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Build Notifio for the current platform or an explicit target."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--macos", action="store_true", help="build Notifio-macOS.zip (macOS only)")
    group.add_argument("--windows", action="store_true", help="build Notifio-Windows.zip (Windows only)")
    args = parser.parse_args(argv)

    target = "macos" if args.macos else "windows" if args.windows else target_for_platform()
    if target is None:
        print("Error: Notifio builds on macOS and Windows only.")
        print("Use the GitHub release workflow for cross-platform releases:")
        print("  .github/workflows/release.yml")
        return 1
    return build(target)


if __name__ == "__main__":
    raise SystemExit(main())