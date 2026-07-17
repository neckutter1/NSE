import os
import sys
import subprocess
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

import display_config

# ── Resource helper (dev + PyInstaller onefile) ───────────────────────────────
def _res(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)

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
        self.geometry("420x310")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self._set_icon()
        self._center()
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
        self.geometry(f"420x310+{(sw - 420) // 2}+{(sh - 310) // 2}")

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
            label="ENGAGE", sublabel="Main display only",
            color=ACCENT, hover=ACCENT_HOVER,
            command=self._engage,
        )
        self._make_action_button(
            btn_row, col=1,
            label="RESTORE", sublabel="Extend all monitors",
            color=RESTORE, hover=RESTORE_HOVER,
            command=self._restore,
        )

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

    @staticmethod
    def _make_action_button(parent, col, label, sublabel, color, hover, command):
        pad_l = (0, 7) if col == 0 else (7, 0)
        cell = ctk.CTkFrame(parent, fg_color=BG)
        cell.grid(row=0, column=col, padx=pad_l, sticky="ew")

        ctk.CTkButton(
            cell,
            text=label,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color=color,
            hover_color=hover,
            text_color="#FFFFFF",
            corner_radius=8,
            height=58,
            command=command,
        ).pack(fill="x")

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

    def _engage(self):
        try:
            ok, err = display_config.engage_primary_only()
        except Exception as exc:  # ctypes/API surprises shouldn't crash the UI
            ok, err = False, str(exc)

        if ok:
            self._status_var.set("NSE engaged")
            self._status_label.configure(text_color=ACCENT)
        else:
            messagebox.showerror(
                "NSE — Error",
                "Could not switch to the primary monitor.\n\n"
                f"{err}",
            )

    def _restore(self):
        if self._run("/extend"):
            self._status_var.set("Extended displays restored")
            self._status_label.configure(text_color=RESTORE_HOVER)


if __name__ == "__main__":
    app = NSEApp()
    app.mainloop()
