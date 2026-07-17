# NSE — Neck Switch Engage

A tiny **Windows** desktop app for one-click switching between "main monitor only"
and "all monitors extended." Two buttons, no menus, no background service.

| Button | What it does |
| --- | --- |
| **ENGAGE** | Keeps **only your primary monitor** active (the one with the taskbar). |
| **RESTORE** | Extends the desktop back across **all** connected monitors. |

ENGAGE targets the primary monitor **by identity** (its desktop position), using the
Windows CCD API (`QueryDisplayConfig` / `SetDisplayConfig`). It does **not** rely on
`DisplaySwitch.exe /internal`, so the correct monitor is kept regardless of your GPU,
graphics driver, or which port each monitor is plugged into.

> **Platform:** Windows only. NSE calls Windows display APIs and won't run on macOS or Linux.

---

## Download (no build required)

If you just want to run it:

1. Go to the [**Releases**](../../releases) page.
2. Download `NSE.exe` from the latest release.
3. Run it. It's a single portable file — no installer, no admin rights.

> **First-run SmartScreen warning:** because the app isn't code-signed, Windows may show
> *"Windows protected your PC."* Click **More info → Run anyway**. This is normal for
> small indie apps. If you're cautious, build it yourself from source (below) instead.

---

## Build from source

Anyone can clone the repo and build their own `NSE.exe`. You need **Windows** and
**Python 3.10+** ([python.org](https://www.python.org/downloads/) — check *"Add Python to PATH"*
during install).

### 1. Clone

```powershell
git clone https://github.com/neckutter1/NSE.git
cd NSE
```

### 2. (Recommended) Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

This installs `customtkinter` (UI), `Pillow` (images), and `pyinstaller` (packaging).

### 4. Build

The easiest path is the included build script, which builds the exe and writes a
SHA-256 checksum for it:

```powershell
.\build.bat
```

Prefer to run PyInstaller directly? Either of these works:

```powershell
pyinstaller NSE.spec
```

```powershell
pyinstaller --noconfirm --onefile --windowed --name NSE ^
    --collect-all customtkinter --add-data "art;art" --icon "art\NSE.ico" main.py
```

Your finished app lands at **`dist\NSE.exe`**.

> If PowerShell blocks `.\build.bat`, run it from **cmd** instead: type `cmd`, then `build.bat`.

---

## Run from source (without building)

Handy for testing changes:

```powershell
python main.py
```

---

## Verifying a download

If you got `NSE.exe` from a Release, confirm it matches the published hash:

```powershell
Get-FileHash dist\NSE.exe -Algorithm SHA256
```

Compare the result against the SHA-256 listed on the Release page.

---

## Project layout

| Path | Purpose |
| --- | --- |
| `main.py` | The app window and buttons (customtkinter UI). |
| `display_config.py` | GPU-agnostic monitor switching via the Windows CCD API. |
| `NSE.spec` | PyInstaller build recipe. |
| `build.bat` | One-click build + checksum script. |
| `requirements.txt` | Python dependencies. |
| `art/` | Icon and banner assets bundled into the exe. |

---

## Notes

- No network access, no telemetry, no background service — it runs only when you open it.
- **RESTORE** uses the built-in `DisplaySwitch.exe /extend`, which is already display-agnostic.
