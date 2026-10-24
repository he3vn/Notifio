# Notifio

Notifio is a notification center for macOS. It pulls together notifications from apps like Discord, Slack, Gmail, GitHub, and others into one clean window so you don't have to keep switching between tabs or apps to check what you missed.

Built with Python and Flet.

---

## How to run it

You'll need Python 3.10 or newer installed on your Mac.

1. Clone the repo:

```
git clone https://github.com/he3vn/Notifio.git
cd Notifio
```

2. Install the dependencies:

```
pip install -r requirements.txt
```

3. Run the app:

```
python3 main.py
```

On first launch you'll go through a short setup where you pick your name and choose which notification sources (plugins) you want enabled. After that it drops you straight into the main dashboard.

---

## Building a standalone app

If you want to package Notifio into a proper .app you can double-click and share with others, run the build script:

```
python3 build.py
```

This will create a `dist/` folder with:
- `Notifio.app` - the standalone Mac app with the custom icon baked in
- `Notifio-macOS.zip` - a zipped version ready to upload to GitHub Releases or send to someone

On Windows it produces an `.exe` and on Linux a standalone binary, same idea.

---

## License

MIT
