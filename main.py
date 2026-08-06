import os
import sys
import ctypes
import subprocess
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

# ── Secondary GPU to power down while gaming ──────────────────────────────────
# Matched against Get-PnpDevice FriendlyName (case-insensitive substring).
SECONDARY_GPU_MATCH = "1050"

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
    """Enable or disable the PnP display adapter matching SECONDARY_GPU_MATCH.
    Returns True if a matching device was found and the command succeeded."""
    verb = "Enable-PnpDevice" if enabled else "Disable-PnpDevice"
    cmd = (
        f"$d = Get-PnpDevice -Class Display -PresentOnly | "
        f"Where-Object {{ $_.FriendlyName -like '*{SECONDARY_GPU_MATCH}*' }}; "
        f"if ($d) {{ $d | {verb} -Confirm:$false; exit 0 }} else {{ exit 1 }}"
    )
    result = _powershell(cmd)
    return result.returncode == 0


# ── Monitor layout save/restore (NirSoft MultiMonitorTool, user-supplied) ──
def _mmt_path() -> str:
    return _res(os.path.join("tools", "MultiMonitorTool.exe"))


def _layout_path() -> str:
    base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "NSE")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "layout.cfg")

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
                f"Could not find/disable a GPU matching "
                f"'{SECONDARY_GPU_MATCH}'. Make sure NSE is running as "
                f"Administrator. Continuing with display switch only.",
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
            self._load_layout()
            self._status_var.set("Extended displays restored")
            self._status_label.configure(text_color=RESTORE_HOVER)
        else:
            self._status_var.set("Ready")

        self._set_buttons_enabled(True)

    def _save_layout(self):
        mmt = _mmt_path()
        if not os.path.isfile(mmt):
            messagebox.showerror(
                "NSE — Error",
                "MultiMonitorTool.exe not found in the tools folder.\n"
                "See tools\\README.txt for where to get it.",
            )
            return
        try:
            subprocess.run(
                [mmt, "/SaveConfig", _layout_path()],
                shell=False,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._status_var.set("Layout saved")
        except subprocess.CalledProcessError as exc:
            messagebox.showerror(
                "NSE — Error",
                f"MultiMonitorTool.exe failed to save the layout.\n\n{exc}",
            )

    def _load_layout(self):
        mmt = _mmt_path()
        layout = _layout_path()
        if os.path.isfile(mmt) and os.path.isfile(layout):
            subprocess.run(
                [mmt, "/LoadConfig", layout],
                shell=False,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )


if __name__ == "__main__":
    if os.name == "nt" and not _is_admin():
        _relaunch_as_admin()
        sys.exit(0)

    app = NSEApp()
    app.mainloop()
