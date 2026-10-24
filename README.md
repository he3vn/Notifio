# Notifio

A beautiful and modern notification center application built with Python and Flet.

---

## 🚀 Running Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/Notifio.git
   cd Notifio
   ```

2. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch Notifio:**
   ```bash
   python3 main.py
   ```

---

## 📦 Building Standalone Binaries

Notifio includes an automated build script `build.py` that packages the application with custom branding and icons:

```bash
python3 build.py
```

### Outputs (in `dist/`):
- **macOS:** `Notifio.app` and `Notifio-macOS.zip` (with `.icns` bundle icon)
- **Windows:** `Notifio.exe` and `Notifio-Windows.zip` (with `.ico` icon)
- **Linux:** `Notifio` binary and `Notifio-Linux.tar.gz` (with `.png` icon)

---

## 🏷️ Publishing Releases to GitHub

The repository is configured with a GitHub Actions workflow (`.github/workflows/release.yml`) for automated multi-platform builds.

### Option 1: Automatic Release via Git Tag
```bash
git tag v1.0.0
git push origin v1.0.0
```
GitHub Actions will automatically build standalone packages for **macOS**, **Windows**, and **Linux**, attach the `.zip` files, and publish the release.

### Option 2: Manual Trigger
1. Go to your repository on GitHub.
2. Click on the **Actions** tab.
3. Select **Build and Release Notifio** in the sidebar.
4. Click **Run workflow**.

---

## 📝 License
MIT
