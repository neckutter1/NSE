import os
import sys
import json
import ctypes
import subprocess
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

# ── Secondary GPU to power down while gaming ──────────────────────────────────
# The GTX 1050 that drives the extra work monitors. Matched by PnP InstanceId,
# which is unique and stable across driver updates; the FriendlyName substring
# is only a fallback in case the card is moved to a different PCIe slot (the
# trailing 4&...&0&0009 encodes bus location and would change if it were).
SECONDARY_GPU_INSTANCE_ID = (
    r"PCI\VEN_10DE&DEV_1C81&SUBSYS_8C971462&REV_A1\4&288DAC85&0&0009"
)
SECONDARY_GPU_MATCH = "GTX 1050"

# The GTX 1080 that drives the primary gaming display. Never disabled; used to
# sanity-check that we are not about to shut off the card we game on.
PRIMARY_GPU_INSTANCE_ID = (
    r"PCI\VEN_10DE&DEV_1B80&SUBSYS_33621462&REV_A1\4&1F822D9D&0&0008"
)

# Milliseconds to wait after re-enabling the GPU before touching display
# topology, so the driver has time to finish reinitializing.
GPU_REINIT_DELAY_MS = 3000

# ── Resource helper (dev + PyInstaller onefile) ───────────────────────────────
def _res(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


# ── Admin elevation ─────────────────────────────────────────────────────────
# Disabling/enabling a PCI device requires an elevated process. The built
# .exe requests elevation via its manifest (see NSE.spec, uac_admin=True);
# this covers running from source with `python main.py` too.
def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_as_admin():
    if getattr(sys, "frozen", False):
        exe = sys.executable
        args = sys.argv[1:]
    else:
        exe = sys.executable
        args = [os.path.abspath(__file__)] + sys.argv[1:]
    params = " ".join(f'"{a}"' for a in args)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)


# ── Secondary GPU control (PnP device disable/enable) ──────────────────────
def _powershell(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
        shell=False,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _set_secondary_gpu_enabled(enabled: bool) -> bool:
    """Enable or disable the secondary GPU.

    Resolves the card by PnP InstanceId first, falling back to a FriendlyName
    match. Refuses to act if the resolved device is the primary GPU, so a bad
    identifier can never blank the display we game on."""
    verb = "Enable-PnpDevice" if enabled else "Disable-PnpDevice"
    cmd = (
        f"$id = '{SECONDARY_GPU_INSTANCE_ID}'; "
        f"$d = Get-PnpDevice -InstanceId $id -ErrorAction SilentlyContinue; "
        f"if (-not $d) {{ "
        f"$d = Get-PnpDevice -Class Display | "
        f"Where-Object {{ $_.FriendlyName -like '*{SECONDARY_GPU_MATCH}*' }} "
        f"}}; "
        f"if (-not $d) {{ exit 2 }}; "
        f"if ($d.InstanceId -eq '{PRIMARY_GPU_INSTANCE_ID}') {{ exit 3 }}; "
        f"$d | {verb} -Confirm:$false -ErrorAction Stop; "
        f"exit 0"
    )
    result = _powershell(cmd)
    return result.returncode == 0


# ── Monitor layout save/restore (native Win32 multi-monitor API) ───────────
# Uses EnumDisplayDevices / EnumDisplaySettingsEx / ChangeDisplaySettingsEx
# directly (the same API Windows itself uses) so no third-party tool is
# needed to capture and reapply monitor position/resolution/orientation.
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
ENUM_CURRENT_SETTINGS = -1

DM_POSITION           = 0x00000020
DM_BITSPERPEL         = 0x00040000
DM_PELSWIDTH          = 0x00080000
DM_PELSHEIGHT         = 0x00100000
DM_DISPLAYFREQUENCY   = 0x00400000
DM_DISPLAYORIENTATION = 0x00000080

CDS_UPDATEREGISTRY = 0x00000001
CDS_NORESET        = 0x10000000


class _DISPLAY_DEVICE(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("DeviceName", ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags", ctypes.c_uint32),
        ("DeviceID", ctypes.c_wchar * 128),
        ("DeviceKey", ctypes.c_wchar * 128),
    ]


class _DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_uint16),
        ("dmDriverVersion", ctypes.c_uint16),
        ("dmSize", ctypes.c_uint16),
        ("dmDriverExtra", ctypes.c_uint16),
        ("dmFields", ctypes.c_uint32),
        ("dmPositionX", ctypes.c_int32),
        ("dmPositionY", ctypes.c_int32),
        ("dmDisplayOrientation", ctypes.c_uint32),
        ("dmDisplayFixedOutput", ctypes.c_uint32),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_uint16),
        ("dmBitsPerPel", ctypes.c_uint32),
        ("dmPelsWidth", ctypes.c_uint32),
        ("dmPelsHeight", ctypes.c_uint32),
        ("dmDisplayFlags", ctypes.c_uint32),
        ("dmDisplayFrequency", ctypes.c_uint32),
        ("dmICMMethod", ctypes.c_uint32),
        ("dmICMIntent", ctypes.c_uint32),
        ("dmMediaType", ctypes.c_uint32),
        ("dmDitherType", ctypes.c_uint32),
        ("dmReserved1", ctypes.c_uint32),
        ("dmReserved2", ctypes.c_uint32),
        ("dmPanningWidth", ctypes.c_uint32),
        ("dmPanningHeight", ctypes.c_uint32),
    ]


def _layout_path() -> str:
    base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "NSE")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "layout.json")


def _enum_active_monitors():
    """Yield (adapter_device_name, stable_monitor_id) for every monitor
    currently attached to the desktop. stable_monitor_id is the monitor's
    own PnP DeviceID (EDID-based) when available, so a saved layout still
    matches up correctly even if \\\\.\\DISPLAYn numbering shifts after the
    secondary GPU is disabled/enabled."""
    user32 = ctypes.windll.user32
    i = 0
    while True:
        dd = _DISPLAY_DEVICE()
        dd.cb = ctypes.sizeof(_DISPLAY_DEVICE)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not (dd.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP):
            continue

        monitor_id = dd.DeviceName
        mon = _DISPLAY_DEVICE()
        mon.cb = ctypes.sizeof(_DISPLAY_DEVICE)
        if user32.EnumDisplayDevicesW(dd.DeviceName, 0, ctypes.byref(mon), 0) and mon.DeviceID:
            monitor_id = mon.DeviceID

        yield dd.DeviceName, monitor_id


def _monitor_count() -> int:
    return sum(1 for _ in _enum_active_monitors())


def _save_layout_native() -> bool:
    user32 = ctypes.windll.user32
    layout = {}
    for device_name, monitor_id in _enum_active_monitors():
        dm = _DEVMODE()
        dm.dmSize = ctypes.sizeof(_DEVMODE)
        if not user32.EnumDisplaySettingsExW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm), 0):
            continue
        layout[monitor_id] = {
            "x": dm.dmPositionX,
            "y": dm.dmPositionY,
            "width": dm.dmPelsWidth,
            "height": dm.dmPelsHeight,
            "freq": dm.dmDisplayFrequency,
            "bpp": dm.dmBitsPerPel,
            "orientation": dm.dmDisplayOrientation,
        }
    if not layout:
        return False
    with open(_layout_path(), "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=2)
    return True


def _load_layout_native() -> bool:
    path = _layout_path()
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        layout = json.load(f)

    user32 = ctypes.windll.user32
    applied = False
    for device_name, monitor_id in _enum_active_monitors():
        saved = layout.get(monitor_id)
        if not saved:
            continue
        dm = _DEVMODE()
        dm.dmSize = ctypes.sizeof(_DEVMODE)
        dm.dmFields = (
            DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT |
            DM_DISPLAYFREQUENCY | DM_BITSPERPEL | DM_DISPLAYORIENTATION
        )
        dm.dmPositionX = saved["x"]
        dm.dmPositionY = saved["y"]
        dm.dmPelsWidth = saved["width"]
        dm.dmPelsHeight = saved["height"]
        dm.dmDisplayFrequency = saved["freq"]
        dm.dmBitsPerPel = saved["bpp"]
        dm.dmDisplayOrientation = saved["orientation"]
        user32.ChangeDisplaySettingsExW(
            device_name, ctypes.byref(dm), None, CDS_UPDATEREGISTRY | CDS_NORESET, None
        )
        applied = True
    if applied:
        user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
    return applied

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── Palette ───────────────────────────────────────────────────────────────────
BG            = "#0D0D0D"
DIVIDER       = "#252525"
ACCENT        = "#D94F00"
ACCENT_HOVER  = "#F06000"
RESTORE       = "#1A5C3A"
RESTORE_HOVER = "#227A4E"
TEXT_MUTED    = "#666666"
TEXT_STATUS   = "#AAAAAA"

# Banner dimensions: keep width at 364px and maintain 4:1 aspect ratio
BANNER_W, BANNER_H = 364, 91


class NSEApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NSE")
        self.geometry("420x350")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self._set_icon()
        self._center()
        self._buttons = []
        self._build_ui()

    # ── Window setup ─────────────────────────────────────────────────────────

    def _set_icon(self):
        ico = _res(os.path.join("art", "NSE.ico"))
        if os.path.isfile(ico):
            self.iconbitmap(ico)

    def _center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"420x350+{(sw - 420) // 2}+{(sh - 350) // 2}")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        root.pack(fill="both", expand=True, padx=28, pady=(16, 12))

        # ── Banner image ──────────────────────────────────────────────────────
        banner_path = _res(os.path.join("art", "NSE_logo_banner.png"))
        if os.path.isfile(banner_path):
            pil_img = Image.open(banner_path)
            banner_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img,
                                      size=(BANNER_W, BANNER_H))
            ctk.CTkLabel(root, image=banner_img, text="").pack()
        else:
            # Fallback plain text header if art is missing
            ctk.CTkLabel(
                root,
                text="NSE",
                font=ctk.CTkFont(family="Segoe UI", size=38, weight="bold"),
                text_color=ACCENT,
            ).pack()

        # ── Divider ───────────────────────────────────────────────────────────
        ctk.CTkFrame(root, height=1, fg_color=DIVIDER).pack(fill="x", pady=(12, 14))

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(root, fg_color=BG)
        btn_row.pack(fill="x")
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self._make_action_button(
            btn_row, col=0,
            label="ENGAGE", sublabel="1080 only — 1050 disabled",
            color=ACCENT, hover=ACCENT_HOVER,
            command=self._engage,
        )
        self._make_action_button(
            btn_row, col=1,
            label="RESTORE", sublabel="Extend all monitors",
            color=RESTORE, hover=RESTORE_HOVER,
            command=self._restore,
        )

        # ── Save layout (one-time setup) ─────────────────────────────────────
        save_btn = ctk.CTkButton(
            root,
            text="SAVE CURRENT LAYOUT",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="transparent",
            hover_color=DIVIDER,
            border_width=1,
            border_color=DIVIDER,
            text_color=TEXT_STATUS,
            corner_radius=8,
            height=30,
            command=self._save_layout,
        )
        save_btn.pack(fill="x", pady=(10, 0))
        self._buttons.append(save_btn)

        # ── Status ────────────────────────────────────────────────────────────
        ctk.CTkFrame(root, height=1, fg_color=DIVIDER).pack(fill="x", pady=(14, 8))

        status_row = ctk.CTkFrame(root, fg_color=BG)
        status_row.pack(fill="x")

        ctk.CTkLabel(
            status_row,
            text="STATUS",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=TEXT_MUTED,
        ).pack(side="left")

        self._status_var = ctk.StringVar(value="Ready")
        self._status_label = ctk.CTkLabel(
            status_row,
            textvariable=self._status_var,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=TEXT_STATUS,
        )
        self._status_label.pack(side="right")

    def _make_action_button(self, parent, col, label, sublabel, color, hover, command):
        pad_l = (0, 7) if col == 0 else (7, 0)
        cell = ctk.CTkFrame(parent, fg_color=BG)
        cell.grid(row=0, column=col, padx=pad_l, sticky="ew")

        btn = ctk.CTkButton(
            cell,
            text=label,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color=color,
            hover_color=hover,
            text_color="#FFFFFF",
            corner_radius=8,
            height=58,
            command=command,
        )
        btn.pack(fill="x")
        self._buttons.append(btn)

        ctk.CTkLabel(
            cell,
            text=sublabel,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=TEXT_MUTED,
        ).pack(pady=(5, 0))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _run(self, arg: str) -> bool:
        try:
            subprocess.run(
                ["DisplaySwitch.exe", arg],
                shell=False,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return True
        except subprocess.CalledProcessError as exc:
            messagebox.showerror(
                "NSE \u2014 Error",
                f"DisplaySwitch.exe exited with an error.\n\n{exc}",
            )
        except FileNotFoundError:
            messagebox.showerror(
                "NSE \u2014 Error",
                "DisplaySwitch.exe was not found.\n"
                "This app requires Windows.",
            )
        return False

    def _set_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for btn in self._buttons:
            btn.configure(state=state)

    def _engage(self):
        self._set_buttons_enabled(False)
        self._status_var.set("Disabling secondary GPU...")
        self.update_idletasks()

        if not _set_secondary_gpu_enabled(False):
            messagebox.showwarning(
                "NSE — Warning",
                f"Could not disable the {SECONDARY_GPU_MATCH}. Make sure NSE "
                f"is running as Administrator.\n\n"
                f"Continuing with display switch only — the card is still "
                f"active, so expect the usual cross-GPU overhead.",
            )

        if self._run("/internal"):
            self._status_var.set("NSE engaged — 1080 only")
            self._status_label.configure(text_color=ACCENT)
        else:
            self._status_var.set("Ready")

        self._set_buttons_enabled(True)

    def _restore(self):
        self._set_buttons_enabled(False)
        self._status_var.set("Re-enabling secondary GPU...")
        self.update_idletasks()

        _set_secondary_gpu_enabled(True)
        self.after(GPU_REINIT_DELAY_MS, self._restore_step2)

    def _restore_step2(self):
        if self._run("/extend"):
            _load_layout_native()
            self._status_var.set("Extended displays restored")
            self._status_label.configure(text_color=RESTORE_HOVER)
        else:
            self._status_var.set("Ready")

        self._set_buttons_enabled(True)

    def _save_layout(self):
        if _save_layout_native():
            self._status_var.set(f"Layout saved ({_monitor_count()} monitors)")
        else:
            messagebox.showerror(
                "NSE — Error",
                "Could not read the current monitor layout.",
            )


if __name__ == "__main__":
    if os.name == "nt" and not _is_admin():
        _relaunch_as_admin()
        sys.exit(0)

    app = NSEApp()
    app.mainloop()
