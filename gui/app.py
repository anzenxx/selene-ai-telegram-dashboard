import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from PIL import Image

import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bot_manager import BotManager
from core.prompt_defaults import DEFAULT_AGENT_PROMPTS
from db.database import (
    add_bot,
    clear_logs,
    delete_bot,
    get_all_bots,
    get_bot,
    get_logs,
    get_stats,
    get_total_stats,
    init_db,
    update_bot,
)
from gui.window_assets import configure_window_assets

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_BG = "#16151C"
SURFACE_BG = "#211E2A"
PANEL_BG = "#292436"
CARD_BG = "#312B42"
CARD_ALT = "#3A3350"
CARD_HOVER = "#463D60"
BORDER = "#564B74"
PRIMARY = "#B6A7E8"
PRIMARY_HOVER = "#C3B5F0"
SECONDARY = "#8FA4D8"
TEXT = "#F5F2FA"
TEXT_MUTED = "#B8AFC7"
TEXT_SOFT = "#9389A6"
SUCCESS = "#8FD2BA"
WARNING = "#DDBB7A"
DANGER = "#D88FA0"
CONSOLE_BG = "#17141F"
GLOW = "#E6DFF4"

CLAUDE_MODELS = [
    "claude-haiku-4-5",
    "claude-sonnet-4-5",
    "claude-opus-4-5",
]

DEFAULT_PROMPTS = DEFAULT_AGENT_PROMPTS

AGENT_EMBLEMS = ["☾", "✦", "✧", "☽", "✹", "❖", "☼", "✺", "⬟", "◐"]

TIMEZONES = [
    "Europe/Kiev",
    "Europe/Moscow",
    "Europe/Berlin",
    "Europe/London",
    "Europe/Warsaw",
    "Europe/Paris",
    "Europe/Istanbul",
    "America/New_York",
    "America/Los_Angeles",
    "Asia/Tokyo",
    "Asia/Dubai",
    "Asia/Shanghai",
    "Asia/Bangkok",
]

CURRENT_VERSION = "Selene Portfolio Preview"
RELEASE_NOTES = [
    {
        "version": "Selene Portfolio Preview",
        "title": "Userbot Workspace",
        "kind": "major",
        "changes": [
            ("new", "Single-window navigation for agents, analytics, activity, and system pages."),
            ("new", "Neutral Telegram userbot positioning for portfolio presentation."),
            ("new", "Embedded agent editor and activity console inside the main workspace."),
        ],
    },
    {
        "version": "5.2",
        "title": "Presence",
        "kind": "patch",
        "changes": [
            ("change", "Response timing profiles refined for active and inactive dialogues."),
            ("change", "Background presence behavior now avoids interrupting active conversations."),
        ],
    },
    {
        "version": "5.0",
        "title": "Token",
        "kind": "major",
        "changes": [
            ("fix", "Debounce pattern rewritten to avoid handling every message as a separate event."),
            ("fix", "Loop scheduling updated from ensure_future to create_task."),
        ],
    },
]


def short_time(value: str) -> str:
    return value[-8:] if value and len(value) >= 8 else value or "--:--:--"


class SectionCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, subtitle: str | None = None):
        super().__init__(
            parent,
            fg_color=CARD_BG,
            corner_radius=20,
            border_width=1,
            border_color=BORDER,
        )
        header = ctk.CTkFrame(self, fg_color=CARD_BG)
        header.pack(fill="x", padx=18, pady=(16, 12))
        ctk.CTkLabel(
            header,
            text=title,
            font=("Segoe UI Semibold", 16),
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                font=("Segoe UI", 11),
                text_color=TEXT_SOFT,
                anchor="w",
            ).pack(anchor="w", pady=(3, 0))

        self.body = ctk.CTkFrame(self, fg_color=CARD_BG)
        self.body.pack(fill="both", expand=True, padx=18, pady=(0, 18))


class MetricCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str, detail: str, accent: str):
        super().__init__(
            parent,
            fg_color=CARD_BG,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        ctk.CTkLabel(self, text=title, text_color=TEXT_SOFT, font=("Segoe UI", 11)).pack(anchor="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(self, text=value, text_color=TEXT, font=("Segoe UI Semibold", 24)).pack(anchor="w", padx=16)
        ctk.CTkLabel(self, text=detail, text_color=accent, font=("Segoe UI", 11)).pack(anchor="w", padx=16, pady=(6, 14))


class AgentFormPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent, on_save, on_cancel):
        super().__init__(parent, fg_color=APP_BG)
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.edit_bot_id = None
        self.mode = "create"

        self.name_var = tk.StringVar(value="SUPPORT")
        self.emblem_var = tk.StringVar(value=AGENT_EMBLEMS[0])
        self.model_var = tk.StringVar(value=CLAUDE_MODELS[0])
        self.timezone_var = tk.StringVar(value=TIMEZONES[0])

        self._build()
        self.load_create_defaults()

    def _field_label(self, parent, text: str):
        ctk.CTkLabel(parent, text=text, text_color=TEXT_MUTED, font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 6))

    def _entry(self, parent, placeholder: str = "", show: str | None = None):
        kwargs = {
            "height": 40,
            "corner_radius": 12,
            "fg_color": SURFACE_BG,
            "border_color": BORDER,
            "text_color": TEXT,
            "font": ("Segoe UI", 12),
            "placeholder_text": placeholder,
        }
        if show:
            kwargs["show"] = show
        return ctk.CTkEntry(parent, **kwargs)

    def _combo(self, parent, values, variable, command=None, width=None):
        kwargs = {
            "values": values,
            "variable": variable,
            "command": command,
            "height": 40,
            "corner_radius": 12,
            "fg_color": SURFACE_BG,
            "border_color": BORDER,
            "button_color": CARD_ALT,
            "button_hover_color": CARD_HOVER,
            "dropdown_fg_color": SURFACE_BG,
            "text_color": TEXT,
            "font": ("Segoe UI", 12),
            "dropdown_font": ("Segoe UI", 12),
        }
        if width is not None:
            kwargs["width"] = width

        widget = ctk.CTkComboBox(
            parent,
            **kwargs,
        )
        return widget
    def _build(self):
        top = ctk.CTkFrame(self, fg_color=APP_BG)
        top.pack(fill="x", pady=(2, 14))
        title_row = ctk.CTkFrame(top, fg_color=APP_BG)
        title_row.pack(fill="x")
        self.title_label = ctk.CTkLabel(title_row, text="Create Agent", font=("Segoe UI Semibold", 24), text_color=TEXT)
        self.title_label.pack(side="left", anchor="w")
        ctk.CTkButton(title_row, text="Back", width=86, height=34, corner_radius=12, fg_color=CARD_ALT, hover_color=CARD_HOVER, text_color=TEXT, command=self.on_cancel).pack(side="right")
        self.subtitle_label = ctk.CTkLabel(
            top,
            text="Configure a Telegram userbot profile, credentials, and response behavior.",
            font=("Segoe UI", 12),
            text_color=TEXT_SOFT,
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 0))

        identity = SectionCard(self, "Identity", "How this userbot appears in the workspace.")
        identity.pack(fill="x", pady=8)
        ident_grid = ctk.CTkFrame(identity.body, fg_color=CARD_BG)
        ident_grid.pack(fill="x")
        ident_grid.grid_columnconfigure(0, weight=1)
        ident_grid.grid_columnconfigure(1, weight=0)

        name_box = ctk.CTkFrame(ident_grid, fg_color=CARD_BG)
        name_box.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._field_label(name_box, "Agent Name")
        self.name_combo = self._combo(name_box, list(DEFAULT_PROMPTS.keys()), self.name_var, command=self._on_name_change)
        self.name_combo.pack(fill="x")

        emblem_box = ctk.CTkFrame(ident_grid, fg_color=CARD_BG)
        emblem_box.grid(row=0, column=1, sticky="ew")
        self._field_label(emblem_box, "Emblem")
        self.emblem_combo = self._combo(emblem_box, AGENT_EMBLEMS, self.emblem_var, width=110)
        self.emblem_combo.pack()

        tz_box = ctk.CTkFrame(identity.body, fg_color=CARD_BG)
        tz_box.pack(fill="x", pady=(14, 0))
        self._field_label(tz_box, "Timezone")
        tz_row = ctk.CTkFrame(tz_box, fg_color=CARD_BG)
        tz_row.pack(fill="x")
        tz_row.grid_columnconfigure(0, weight=1)
        self.timezone_combo = self._combo(tz_row, TIMEZONES, self.timezone_var)
        self.timezone_combo.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(
            tz_row,
            text="Add",
            width=74,
            height=40,
            corner_radius=12,
            fg_color=CARD_ALT,
            hover_color=CARD_HOVER,
            text_color=TEXT,
            command=self._add_timezone,
        ).grid(row=0, column=1)

        creds = SectionCard(self, "Telegram Access", "Credentials for the Telegram account used by this agent.")
        creds.pack(fill="x", pady=8)
        self._field_label(creds.body, "Telegram API ID")
        self.api_id_entry = self._entry(creds.body, "12345678")
        self.api_id_entry.pack(fill="x")
        self._field_label(creds.body, "Telegram API Hash")
        self.api_hash_entry = self._entry(creds.body, "Telegram API Hash", show="*")
        self.api_hash_entry.pack(fill="x")
        self._field_label(creds.body, "Phone Number")
        self.phone_entry = self._entry(creds.body, "+79001234567")
        self.phone_entry.pack(fill="x")

        ai = SectionCard(self, "AI Configuration", "Model, API key, and generation limits.")
        ai.pack(fill="x", pady=8)
        self._field_label(ai.body, "Anthropic API Key")
        self.anthropic_entry = self._entry(ai.body, "sk-ant-...", show="*")
        self.anthropic_entry.pack(fill="x")

        ai_row = ctk.CTkFrame(ai.body, fg_color=CARD_BG)
        ai_row.pack(fill="x", pady=(14, 0))
        ai_row.grid_columnconfigure(0, weight=1)
        ai_row.grid_columnconfigure(1, weight=1)

        model_box = ctk.CTkFrame(ai_row, fg_color=CARD_BG)
        model_box.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._field_label(model_box, "Claude Model")
        self.model_combo = self._combo(model_box, CLAUDE_MODELS, self.model_var)
        self.model_combo.pack(fill="x")

        token_box = ctk.CTkFrame(ai_row, fg_color=CARD_BG)
        token_box.grid(row=0, column=1, sticky="ew")
        self._field_label(token_box, "Max Tokens")
        self.max_tokens_entry = self._entry(token_box, "512")
        self.max_tokens_entry.pack(fill="x")

        behavior = SectionCard(self, "Behavior", "How the agent is triggered and how it should respond.")
        behavior.pack(fill="x", pady=8)
        self._field_label(behavior.body, "Trigger Prefix (leave empty for all private messages)")
        self.trigger_entry = self._entry(behavior.body, ".ai")
        self.trigger_entry.pack(fill="x")
        self._field_label(behavior.body, "System Prompt")
        self.prompt_text = ctk.CTkTextbox(
            behavior.body,
            height=210,
            fg_color=SURFACE_BG,
            border_color=BORDER,
            border_width=1,
            text_color=TEXT,
            font=("Segoe UI", 12),
            corner_radius=14,
        )
        self.prompt_text.pack(fill="x")

        footer = ctk.CTkFrame(self, fg_color=APP_BG)
        footer.pack(fill="x", pady=(14, 10))
        ctk.CTkButton(
            footer,
            text="Cancel",
            width=110,
            height=42,
            corner_radius=14,
            fg_color=CARD_ALT,
            hover_color=CARD_HOVER,
            text_color=TEXT,
            command=self.on_cancel,
        ).pack(side="left")
        self.save_button = ctk.CTkButton(
            footer,
            text="Save Agent",
            width=140,
            height=42,
            corner_radius=14,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color=APP_BG,
            font=("Segoe UI Semibold", 12),
            command=self._submit,
        )
        self.save_button.pack(side="right")

    def _clear_entries(self):
        for entry in [
            self.api_id_entry,
            self.api_hash_entry,
            self.phone_entry,
            self.anthropic_entry,
            self.max_tokens_entry,
            self.trigger_entry,
        ]:
            entry.delete(0, "end")
        self.prompt_text.delete("1.0", "end")

    def load_create_defaults(self):
        self.mode = "create"
        self.edit_bot_id = None
        self.title_label.configure(text="Create Agent")
        self.subtitle_label.configure(text="Configure a Telegram userbot profile, credentials, and response behavior.")
        self.save_button.configure(text="Save Agent")
        self._clear_entries()
        self.name_var.set(list(DEFAULT_PROMPTS.keys())[0])
        self.emblem_var.set(AGENT_EMBLEMS[0])
        self.model_var.set(CLAUDE_MODELS[0])
        self.timezone_var.set(TIMEZONES[0])
        self.max_tokens_entry.insert(0, "512")
        self.trigger_entry.insert(0, ".ai")
        self.prompt_text.insert("1.0", DEFAULT_PROMPTS[self.name_var.get()])

    def load_bot(self, bot_id: int):
        cfg = get_bot(bot_id)
        if not cfg:
            return
        self.mode = "edit"
        self.edit_bot_id = bot_id
        self.title_label.configure(text="Edit Agent")
        self.subtitle_label.configure(text="Refine the userbot identity, access, and behavior without leaving the main workspace.")
        self.save_button.configure(text="Update Agent")
        self._clear_entries()

        self.name_var.set((cfg.get("name") or list(DEFAULT_PROMPTS.keys())[0]).upper())
        self.emblem_var.set(cfg.get("emoji") or AGENT_EMBLEMS[0])
        self.model_var.set(cfg.get("claude_model") or CLAUDE_MODELS[0])
        self.timezone_var.set(cfg.get("timezone") or TIMEZONES[0])

        self.api_id_entry.insert(0, cfg.get("api_id", ""))
        self.api_hash_entry.insert(0, cfg.get("api_hash", ""))
        self.phone_entry.insert(0, cfg.get("phone", ""))
        self.anthropic_entry.insert(0, cfg.get("anthropic_key", ""))
        self.max_tokens_entry.insert(0, str(cfg.get("max_tokens", 512)))
        self.trigger_entry.insert(0, cfg.get("trigger_prefix", ""))
        self.prompt_text.insert("1.0", cfg.get("system_prompt", ""))

    def _on_name_change(self, value):
        if self.mode == "create":
            self.prompt_text.delete("1.0", "end")
            self.prompt_text.insert("1.0", DEFAULT_PROMPTS.get(value, ""))

    def _add_timezone(self):
        dialog = ctk.CTkInputDialog(text="Enter an IANA timezone, for example Europe/Berlin.", title="Add Timezone")
        tz = dialog.get_input()
        if not tz:
            return
        tz = tz.strip()
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(tz)
        except Exception:
            messagebox.showerror("Invalid timezone", f"Timezone '{tz}' is not recognized.")
            return

        values = list(self.timezone_combo.cget("values"))
        if tz not in values:
            values.append(tz)
            self.timezone_combo.configure(values=values)
        self.timezone_var.set(tz)

    def _submit(self):
        name = self.name_var.get().strip()
        emoji = self.emblem_var.get().strip() or AGENT_EMBLEMS[0]
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        phone = self.phone_entry.get().strip()
        anthropic_key = self.anthropic_entry.get().strip()
        model = self.model_var.get().strip()
        trigger_prefix = self.trigger_entry.get().strip()
        prompt = self.prompt_text.get("1.0", "end").strip()
        timezone = self.timezone_var.get().strip() or TIMEZONES[0]

        try:
            max_tokens = int((self.max_tokens_entry.get() or "512").strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Max Tokens must be a number.")
            return

        if not all([name, api_id, api_hash, phone, anthropic_key]):
            messagebox.showerror("Missing information", "Please fill in all required credentials.")
            return

        payload = dict(
            name=name,
            emoji=emoji,
            api_id=api_id,
            api_hash=api_hash,
            phone=phone,
            anthropic_key=anthropic_key,
            claude_model=model,
            system_prompt=prompt,
            trigger_prefix=trigger_prefix,
            max_tokens=max_tokens,
            timezone=timezone,
        )
        self.on_save(self.edit_bot_id, payload)


class SeleneApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        init_db()

        self.live_logs: dict[int, list] = {}
        self.manager = BotManager(log_callback=self._on_log, state_callback=self._on_bot_state)
        self.selected_bot_id: int | None = None
        self.current_agents_mode = "overview"
        self.current_page_key = "agents"
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.agent_cards: dict[int, ctk.CTkFrame] = {}
        self._brand_image = None
        self._window_icon = None
        self._window_icon_images = []
        self._brand_logo_small = None
        self._brand_logo_large = None

        self.title("Selene")
        self.geometry("1420x880")
        self.minsize(1180, 760)
        self.configure(fg_color=APP_BG)

        self._configure_icon()
        os.makedirs("sessions", exist_ok=True)

        self.manager.load_bots()
        self._build_shell()
        self.refresh_all_views(keep_selection=False)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
    def _configure_icon(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        source = configure_window_assets(self, os.path.join(base_dir, "assets"))
        if source is None:
            self._brand_image = None
            self._window_icon = None
            self._window_icon_images = []
            self._brand_logo_small = None
            self._brand_logo_large = None
            return

        self._brand_image = ctk.CTkImage(light_image=source, dark_image=source, size=(160, 160))
        self._brand_logo_small = ctk.CTkImage(light_image=source, dark_image=source, size=(28, 28))
        self._brand_logo_large = ctk.CTkImage(light_image=source, dark_image=source, size=(76, 76))

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self,
            fg_color=SURFACE_BG,
            corner_radius=0,
            border_width=0,
            width=260,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        self.content = ctk.CTkFrame(self, fg_color=APP_BG)
        self.content.grid(row=0, column=1, sticky="nsew", padx=(0, 18), pady=18)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_header()
        self._build_pages()
        self.show_page("agents")

    def _build_sidebar(self):
        brand = ctk.CTkFrame(self.sidebar, fg_color=SURFACE_BG)
        brand.pack(fill="x", padx=20, pady=(22, 18))

        logo_row = ctk.CTkFrame(brand, fg_color=SURFACE_BG)
        logo_row.pack(fill="x")
        if self._brand_logo_small is not None:
            ctk.CTkLabel(logo_row, text="", image=self._brand_logo_small).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(logo_row, text="Selene", font=("Segoe UI Semibold", 24), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(
            brand,
            text="Control Center for Telegram Userbots",
            font=("Segoe UI", 11),
            text_color=TEXT_SOFT,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        ctk.CTkFrame(self.sidebar, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=(0, 16))

        nav_items = [
            ("agents", "Agents"),
            ("analytics", "Analytics"),
            ("activity", "Activity"),
            ("system", "System"),
        ]
        for key, label in nav_items:
            button = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=44,
                corner_radius=14,
                fg_color=SURFACE_BG,
                hover_color=CARD_HOVER,
                text_color=TEXT,
                font=("Segoe UI Semibold", 13),
                command=lambda k=key: self.show_page(k),
            )
            button.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[key] = button

        ctk.CTkLabel(self.sidebar, text="Updates", text_color=TEXT_SOFT, font=("Segoe UI", 11)).pack(anchor="w", padx=20, pady=(22, 6))
        release_btn = ctk.CTkButton(
            self.sidebar,
            text="Release Notes",
            anchor="w",
            height=40,
            corner_radius=14,
            fg_color=SURFACE_BG,
            hover_color=CARD_HOVER,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            command=lambda: self.show_page("release"),
        )
        release_btn.pack(fill="x", padx=14)
        self.nav_buttons["release"] = release_btn

        self.sidebar_status = ctk.CTkFrame(self.sidebar, fg_color=CARD_BG, corner_radius=18, border_width=1, border_color=BORDER)
        self.sidebar_status.pack(fill="x", padx=14, pady=(28, 14), side="bottom")
        self.sidebar_status.pack_propagate(False)
        ctk.CTkLabel(self.sidebar_status, text="Userbot Network", text_color=TEXT_SOFT, font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=(14, 4))
        self.sidebar_status_value = ctk.CTkLabel(self.sidebar_status, text="0 active agents", text_color=TEXT, font=("Segoe UI Semibold", 16))
        self.sidebar_status_value.pack(anchor="w", padx=14)
        self.sidebar_status_hint = ctk.CTkLabel(self.sidebar_status, text="Monitoring is centralized in one quiet workspace.", text_color=PRIMARY, font=("Segoe UI", 10), justify="left")
        self.sidebar_status_hint.pack(anchor="w", padx=14, pady=(4, 14))

    def _build_header(self):
        header = ctk.CTkFrame(self.content, fg_color=SURFACE_BG, corner_radius=20, border_width=1, border_color=BORDER)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(header, fg_color=SURFACE_BG)
        left.grid(row=0, column=0, sticky="w", padx=22, pady=18)
        self.header_title = ctk.CTkLabel(left, text="Agents", font=("Segoe UI Semibold", 26), text_color=TEXT)
        self.header_title.pack(anchor="w")
        self.header_subtitle = ctk.CTkLabel(left, text="Monitor Telegram userbots, prompts, sessions, and activity from one workspace.", font=("Segoe UI", 12), text_color=TEXT_SOFT)
        self.header_subtitle.pack(anchor="w", pady=(4, 0))

        right = ctk.CTkFrame(header, fg_color=SURFACE_BG)
        right.grid(row=0, column=1, sticky="e", padx=22, pady=16)
        self.header_chip = ctk.CTkFrame(right, fg_color=CARD_BG, corner_radius=16, border_width=1, border_color=BORDER)
        self.header_chip.pack(anchor="e")
        self.header_chip_label = ctk.CTkLabel(self.header_chip, text="System Calm", text_color=SUCCESS, font=("Segoe UI Semibold", 11))
        self.header_chip_label.pack(padx=14, pady=10)

    def _build_pages(self):
        stack = ctk.CTkFrame(self.content, fg_color=APP_BG)
        stack.grid(row=1, column=0, sticky="nsew")
        stack.grid_rowconfigure(0, weight=1)
        stack.grid_columnconfigure(0, weight=1)
        self.page_stack = stack

        self.pages["agents"] = self._build_agents_page()
        self.pages["analytics"] = self._build_analytics_page()
        self.pages["activity"] = self._build_activity_page()
        self.pages["system"] = self._build_system_page()
        self.pages["release"] = self._build_release_page()

        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

    def _build_agents_page(self):
        page = ctk.CTkFrame(self.page_stack, fg_color=APP_BG)
        page.grid_columnconfigure(0, weight=1, minsize=330)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(1, weight=1)

        hero = ctk.CTkFrame(page, fg_color=PANEL_BG, corner_radius=22, border_width=1, border_color=BORDER)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        hero.grid_columnconfigure(0, weight=1)
        hero.grid_columnconfigure(1, weight=0)
        ctk.CTkLabel(hero, text="Agent Constellation", font=("Segoe UI Semibold", 22), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(hero, text="Select an agent to inspect, then launch, stop, edit, or prepare a session without leaving this page.", font=("Segoe UI", 12), text_color=TEXT_SOFT).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 18))
        ctk.CTkButton(
            hero,
            text="Create Agent",
            width=136,
            height=42,
            corner_radius=14,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color=APP_BG,
            font=("Segoe UI Semibold", 12),
            command=self.start_create_agent,
        ).grid(row=0, column=1, rowspan=2, padx=20, pady=18)

        left_panel = ctk.CTkFrame(page, fg_color=APP_BG)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        list_header = SectionCard(left_panel, "Agents", "Every configured identity, with live status at a glance.")
        list_header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        stats_row = ctk.CTkFrame(list_header.body, fg_color=CARD_BG)
        stats_row.pack(fill="x")
        self.agents_count_value = ctk.CTkLabel(stats_row, text="0 configured", font=("Segoe UI Semibold", 18), text_color=TEXT)
        self.agents_count_value.pack(side="left")
        self.agents_count_hint = ctk.CTkLabel(stats_row, text="0 active", font=("Segoe UI", 11), text_color=TEXT_SOFT)
        self.agents_count_hint.pack(side="right")

        self.agent_list = ctk.CTkScrollableFrame(left_panel, fg_color=APP_BG)
        self.agent_list.grid(row=1, column=0, sticky="nsew")

        self.agent_workspace = ctk.CTkFrame(page, fg_color=APP_BG)
        self.agent_workspace.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.agent_workspace.grid_rowconfigure(0, weight=1)
        self.agent_workspace.grid_columnconfigure(0, weight=1)

        self.agent_detail_view = self._build_agent_detail_view(self.agent_workspace)
        self.agent_detail_view.grid(row=0, column=0, sticky="nsew")

        self.agent_form_view = AgentFormPanel(
            self.agent_workspace,
            on_save=self.save_agent,
            on_cancel=self.exit_agent_form,
        )
        self.agent_form_view.grid(row=0, column=0, sticky="nsew")
        self.agent_form_view.grid_remove()

        return page

    def _build_agent_detail_view(self, parent):
        wrapper = ctk.CTkFrame(parent, fg_color=APP_BG)
        wrapper.grid_rowconfigure(2, weight=1)
        wrapper.grid_columnconfigure(0, weight=1)

        self.agent_overview_card = SectionCard(wrapper, "Selected Agent", "Detailed identity, behavior, and control actions.")
        self.agent_overview_card.grid(row=0, column=0, sticky="ew")
        self.agent_overview_card.body.grid_columnconfigure(0, weight=1)
        self.agent_overview_card.body.grid_columnconfigure(1, weight=0)

        identity = ctk.CTkFrame(self.agent_overview_card.body, fg_color=CARD_BG)
        identity.grid(row=0, column=0, sticky="w")
        self.selected_emblem = ctk.CTkLabel(identity, text="☾", font=("Segoe UI Symbol", 28), text_color=PRIMARY)
        self.selected_emblem.pack(anchor="w")
        self.selected_name = ctk.CTkLabel(identity, text="No agent selected", font=("Segoe UI Semibold", 28), text_color=TEXT)
        self.selected_name.pack(anchor="w", pady=(2, 0))
        self.selected_meta = ctk.CTkLabel(identity, text="Choose an agent from the left to inspect its status and controls.", font=("Segoe UI", 12), text_color=TEXT_SOFT, justify="left")
        self.selected_meta.pack(anchor="w", pady=(6, 0))

        action_box = ctk.CTkFrame(self.agent_overview_card.body, fg_color=CARD_BG)
        action_box.grid(row=0, column=1, sticky="e")
        self.launch_button = ctk.CTkButton(action_box, text="Launch", width=110, height=40, corner_radius=14, fg_color=SUCCESS, hover_color="#91E7CB", text_color=APP_BG, font=("Segoe UI Semibold", 12), command=self.toggle_selected_bot)
        self.launch_button.pack(pady=4)
        self.edit_button = ctk.CTkButton(action_box, text="Edit", width=110, height=40, corner_radius=14, fg_color=CARD_ALT, hover_color=CARD_HOVER, text_color=TEXT, font=("Segoe UI Semibold", 12), command=self.start_edit_selected_agent)
        self.edit_button.pack(pady=4)
        self.session_button = ctk.CTkButton(action_box, text="Session", width=110, height=40, corner_radius=14, fg_color=CARD_ALT, hover_color=CARD_HOVER, text_color=TEXT, font=("Segoe UI Semibold", 12), command=self.create_session_for_selected)
        self.session_button.pack(pady=4)
        self.delete_button = ctk.CTkButton(action_box, text="Delete", width=110, height=40, corner_radius=14, fg_color="#402342", hover_color="#553059", text_color=DANGER, font=("Segoe UI Semibold", 12), command=self.delete_selected_agent)
        self.delete_button.pack(pady=4)
        self.info_grid = ctk.CTkFrame(wrapper, fg_color=APP_BG)
        self.info_grid.grid(row=1, column=0, sticky="ew", pady=16)
        for column in range(3):
            self.info_grid.grid_columnconfigure(column, weight=1)
        self.info_labels = {}
        for idx, title in enumerate(["Model", "Trigger", "Timezone"]):
            card = SectionCard(self.info_grid, title)
            card.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 8, 0))
            value = ctk.CTkLabel(card.body, text="--", text_color=TEXT, font=("Segoe UI Semibold", 18))
            value.pack(anchor="w")
            self.info_labels[title.lower()] = value

        lower = ctk.CTkFrame(wrapper, fg_color=APP_BG)
        lower.grid(row=2, column=0, sticky="nsew")
        lower.grid_columnconfigure(0, weight=2)
        lower.grid_columnconfigure(1, weight=1)
        lower.grid_rowconfigure(0, weight=1)

        prompt_card = SectionCard(lower, "Prompt Profile", "The current behavioral brief used by the selected agent.")
        prompt_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.prompt_preview = ctk.CTkTextbox(prompt_card.body, fg_color=SURFACE_BG, border_color=BORDER, border_width=1, text_color=TEXT, font=("Segoe UI", 12), corner_radius=14)
        self.prompt_preview.pack(fill="both", expand=True)
        self.prompt_preview.configure(state="disabled")

        recent_card = SectionCard(lower, "Recent Activity", "Latest events for the selected agent, updated live when possible.")
        recent_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.recent_activity_box = ctk.CTkTextbox(recent_card.body, fg_color=CONSOLE_BG, border_color=BORDER, border_width=1, text_color=GLOW, font=("Cascadia Code", 11), corner_radius=14)
        self.recent_activity_box.pack(fill="both", expand=True)
        self.recent_activity_box.configure(state="disabled")
        self._set_agent_action_state(False)

        return wrapper

    def _build_analytics_page(self):
        page = ctk.CTkScrollableFrame(self.page_stack, fg_color=APP_BG)

        top = ctk.CTkFrame(page, fg_color=APP_BG)
        top.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(top, text="Analytics", font=("Segoe UI Semibold", 24), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(top, text="Seven-day message volume and token usage by managed userbot.", font=("Segoe UI", 12), text_color=TEXT_SOFT).pack(anchor="w", pady=(4, 0))

        metrics = ctk.CTkFrame(page, fg_color=APP_BG)
        metrics.pack(fill="x", pady=(0, 16))
        for column in range(4):
            metrics.grid_columnconfigure(column, weight=1)
        self.analytics_metric_cards = {}
        for idx, (key, title, accent) in enumerate([
            ("agents", "Configured Agents", PRIMARY),
            ("active", "Active Now", SUCCESS),
            ("messages", "Messages (7d)", WARNING),
            ("tokens", "Tokens (7d)", SECONDARY),
        ]):
            card = MetricCard(metrics, title, "0", "Awaiting data", accent)
            card.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 8, 0), pady=4)
            self.analytics_metric_cards[key] = card

        self.analytics_list = ctk.CTkFrame(page, fg_color=APP_BG)
        self.analytics_list.pack(fill="both", expand=True)
        return page

    def _build_activity_page(self):
        page = ctk.CTkFrame(self.page_stack, fg_color=APP_BG)
        page.grid_columnconfigure(0, weight=1, minsize=260)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(0, weight=1)

        left = SectionCard(page, "Activity Lens", "Choose which agent feed you want to inspect.")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.activity_agent_list = ctk.CTkScrollableFrame(left.body, fg_color=APP_BG)
        self.activity_agent_list.pack(fill="both", expand=True)

        right = SectionCard(page, "Premium Console", "Live entries appear here when available. Historical logs are loaded from the database.")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        tool_row = ctk.CTkFrame(right.body, fg_color=CARD_BG)
        tool_row.pack(fill="x", pady=(0, 12))
        self.activity_title = ctk.CTkLabel(tool_row, text="All quiet", font=("Segoe UI Semibold", 18), text_color=TEXT)
        self.activity_title.pack(side="left")
        ctk.CTkButton(tool_row, text="Clear Logs", width=100, height=34, corner_radius=12, fg_color="#402342", hover_color="#553059", text_color=DANGER, command=self.clear_selected_logs).pack(side="right")
        ctk.CTkButton(tool_row, text="Refresh", width=90, height=34, corner_radius=12, fg_color=CARD_ALT, hover_color=CARD_HOVER, text_color=TEXT, command=self.refresh_activity_feed).pack(side="right", padx=(0, 10))
        self.activity_console = ctk.CTkTextbox(right.body, fg_color=CONSOLE_BG, border_color=BORDER, border_width=1, text_color=GLOW, font=("Cascadia Code", 11), corner_radius=16)
        self.activity_console.pack(fill="both", expand=True)
        self.activity_console.configure(state="disabled")
        return page

    def _build_system_page(self):
        page = ctk.CTkScrollableFrame(self.page_stack, fg_color=APP_BG)

        hero = ctk.CTkFrame(page, fg_color=PANEL_BG, corner_radius=24, border_width=1, border_color=BORDER)
        hero.pack(fill="x", pady=(0, 16))
        hero.grid_columnconfigure(1, weight=1)
        if self._brand_logo_large is not None:
            ctk.CTkLabel(hero, text="", image=self._brand_logo_large).grid(row=0, column=0, rowspan=2, padx=22, pady=22)
        ctk.CTkLabel(hero, text="Selene", font=("Segoe UI Semibold", 30), text_color=TEXT).grid(row=0, column=1, sticky="w", pady=(24, 4))
        ctk.CTkLabel(hero, text="Control Center for Telegram Userbots", font=("Segoe UI", 13), text_color=PRIMARY).grid(row=1, column=1, sticky="w", pady=(0, 24))
        ctk.CTkLabel(hero, text="A calmer command layer for launching, refining, and monitoring AI-driven Telegram agents.", font=("Segoe UI", 12), text_color=TEXT_SOFT, justify="left").grid(row=2, column=0, columnspan=2, sticky="w", padx=22, pady=(0, 22))

        stack = ctk.CTkFrame(page, fg_color=APP_BG)
        stack.pack(fill="both", expand=True)
        for column in range(2):
            stack.grid_columnconfigure(column, weight=1)

        info = SectionCard(stack, "Platform Overview", "Core building blocks behind this userbot manager.")
        info.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)
        for label, value in [
            ("Interface", "CustomTkinter desktop workspace"),
            ("Messaging", "Telethon Telegram client API"),
            ("Language Model", "Anthropic Claude"),
            ("Storage", "SQLite local database"),
        ]:
            row = ctk.CTkFrame(info.body, fg_color=CARD_BG)
            row.pack(fill="x", pady=6)
            ctk.CTkLabel(row, text=label, text_color=TEXT_SOFT, font=("Segoe UI", 11), width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, text_color=TEXT, font=("Segoe UI Semibold", 12), anchor="w").pack(side="left")

        runtime = SectionCard(stack, "Runtime State", "Live system summary collected from the current session.")
        runtime.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=8)
        self.system_runtime_box = ctk.CTkTextbox(runtime.body, height=180, fg_color=SURFACE_BG, border_color=BORDER, border_width=1, text_color=TEXT, font=("Cascadia Code", 11), corner_radius=14)
        self.system_runtime_box.pack(fill="both", expand=True)
        self.system_runtime_box.configure(state="disabled")

        notes = SectionCard(page, "Design Intent", "What this portfolio-ready redesign is trying to achieve.")
        notes.pack(fill="x", pady=8)
        ctk.CTkLabel(
            notes.body,
            text="Selene presents Telegram account automation as a neutral operations tool: credentials, prompts, sessions, logs, and analytics are managed in one focused workspace.",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            justify="left",
            wraplength=920,
        ).pack(anchor="w")
        return page

    def _build_release_page(self):
        page = ctk.CTkScrollableFrame(self.page_stack, fg_color=APP_BG)
        ctk.CTkLabel(page, text="Release Notes", font=("Segoe UI Semibold", 24), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(page, text="A quieter corner for version history and recent improvements.", font=("Segoe UI", 12), text_color=TEXT_SOFT).pack(anchor="w", pady=(4, 16))

        color_map = {
            "major": PRIMARY,
            "patch": SECONDARY,
            "hotfix": DANGER,
        }
        kind_map = {
            "new": PRIMARY,
            "fix": SUCCESS,
            "change": WARNING,
        }
        for entry in RELEASE_NOTES:
            card = SectionCard(page, f"{entry['version']} · {entry['title']}")
            card.pack(fill="x", pady=8)
            ctk.CTkLabel(card.body, text=entry["kind"].upper(), text_color=color_map.get(entry["kind"], PRIMARY), font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 10))
            for change_kind, text in entry["changes"]:
                row = ctk.CTkFrame(card.body, fg_color=CARD_BG)
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=change_kind.upper(), text_color=kind_map.get(change_kind, TEXT_SOFT), font=("Segoe UI Semibold", 10), width=70, anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=text, text_color=TEXT_MUTED, font=("Segoe UI", 12), justify="left", wraplength=920).pack(side="left", fill="x")
        return page
    def show_page(self, key: str):
        if key != "agents" and self.current_agents_mode == "form":
            self.exit_agent_form()
        self.current_page_key = key
        for name, page in self.pages.items():
            if name == key:
                page.grid()
                page.tkraise()
            else:
                page.grid_remove()

        page = self.pages[key]
        page.tkraise()

        titles = {
            "agents": ("Agents", "Monitor Telegram userbots, prompts, sessions, and activity from one workspace."),
            "analytics": ("Analytics", "Track message volume, token load, and overall activity without noise."),
            "activity": ("Activity", "Inspect the live console feed and clear historical logs when needed."),
            "system": ("System", "The platform stack, runtime summary, and local configuration overview."),
            "release": ("Release Notes", "A less prominent stream of changes and milestones."),
        }
        title, subtitle = titles[key]
        self.header_title.configure(text=title)
        self.header_subtitle.configure(text=subtitle)

        for name, button in self.nav_buttons.items():
            active = name == key
            button.configure(
                fg_color=CARD_ALT if active else SURFACE_BG,
                text_color=TEXT if active else (TEXT_MUTED if name == "release" else TEXT),
                border_width=1 if active else 0,
                border_color=BORDER,
            )

        if key == "analytics":
            self.refresh_analytics_page()
        elif key == "activity":
            self.refresh_activity_feed()
        elif key == "system":
            self.refresh_system_page()

    def refresh_all_views(self, keep_selection: bool = True):
        previous = self.selected_bot_id if keep_selection else None
        bots = get_all_bots()
        self.manager.load_bots()
        self._render_agent_list(bots)
        self._render_activity_agent_list(bots)
        self._update_sidebar_metrics(bots)
        self.refresh_analytics_page(bots)
        self.refresh_system_page(bots)

        valid_ids = {cfg["id"] for cfg in bots}
        if previous in valid_ids:
            self.select_bot(previous, sync_activity=False)
        elif bots:
            self.select_bot(bots[0]["id"], sync_activity=False)
        else:
            self.selected_bot_id = None
            self._render_selected_agent(None)
            self._clear_activity_console("No agents configured yet.")

    def _render_agent_list(self, bots):
        for widget in self.agent_list.winfo_children():
            widget.destroy()
        self.agent_cards.clear()

        active_count = sum(1 for cfg in bots if self.manager.is_running(cfg["id"]))
        self.agents_count_value.configure(text=f"{len(bots)} configured")
        self.agents_count_hint.configure(text=f"{active_count} active")

        if not bots:
            empty = SectionCard(self.agent_list, "No agents yet", "Create your first identity to start the constellation.")
            empty.pack(fill="x", pady=8)
            ctk.CTkButton(empty.body, text="Create Agent", width=130, height=40, corner_radius=14, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color=APP_BG, command=self.start_create_agent).pack(anchor="w")
            return

        for cfg in bots:
            running = self.manager.is_running(cfg["id"])
            card = ctk.CTkFrame(self.agent_list, fg_color=CARD_BG, corner_radius=18, border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=6)

            row = ctk.CTkFrame(card, fg_color=CARD_BG)
            row.pack(fill="x", padx=16, pady=14)
            emblem = ctk.CTkLabel(row, text=cfg.get("emoji") or "☾", font=("Segoe UI Symbol", 22), text_color=PRIMARY)
            emblem.pack(side="left")

            text_box = ctk.CTkFrame(row, fg_color=CARD_BG)
            text_box.pack(side="left", fill="x", expand=True, padx=(12, 0))
            name_label = ctk.CTkLabel(text_box, text=cfg["name"], text_color=TEXT, font=("Segoe UI Semibold", 15))
            name_label.pack(anchor="w")
            meta_label = ctk.CTkLabel(text_box, text=cfg.get("claude_model", "Claude") + "  ·  " + (cfg.get("timezone") or "Timezone"), text_color=TEXT_SOFT, font=("Segoe UI", 11))
            meta_label.pack(anchor="w", pady=(3, 0))

            state_text = "Online" if running else "Standby"
            state_color = SUCCESS if running else TEXT_SOFT
            state_label = ctk.CTkLabel(row, text=state_text, text_color=state_color, font=("Segoe UI Semibold", 11))
            state_label.pack(side="right")

            self._bind_card_click(
                [card, row, emblem, text_box, name_label, meta_label, state_label],
                lambda bot_id=cfg["id"]: self.select_bot(bot_id),
            )

            self.agent_cards[cfg["id"]] = card

    def _bind_card_click(self, widgets, callback):
        for widget in widgets:
            widget.bind("<Button-1>", lambda _event, cb=callback: cb())

    def _render_activity_agent_list(self, bots):
        for widget in self.activity_agent_list.winfo_children():
            widget.destroy()

        for cfg in bots:
            running = self.manager.is_running(cfg["id"])
            button = ctk.CTkButton(
                self.activity_agent_list,
                text=f"{cfg.get('emoji') or '☾'}  {cfg['name']}",
                anchor="w",
                height=42,
                corner_radius=14,
                fg_color=CARD_ALT if cfg["id"] == self.selected_bot_id else CARD_BG,
                hover_color=CARD_HOVER,
                text_color=TEXT if running else TEXT_MUTED,
                font=("Segoe UI Semibold", 12),
                command=lambda bot_id=cfg["id"]: self.select_bot(bot_id),
            )
            button.pack(fill="x", pady=4)

    def _update_sidebar_metrics(self, bots):
        active_count = sum(1 for cfg in bots if self.manager.is_running(cfg["id"]))
        self.sidebar_status_value.configure(text=f"{active_count} active agents")
        if active_count:
            self.header_chip_label.configure(text="System Awake", text_color=SUCCESS)
        else:
            self.header_chip_label.configure(text="System Calm", text_color=PRIMARY)

    def select_bot(self, bot_id: int, sync_activity: bool = True):
        if self.current_agents_mode == "form":
            self.exit_agent_form()
        self.selected_bot_id = bot_id
        cfg = get_bot(bot_id)
        self._render_selected_agent(cfg)
        self._highlight_selected_agent(bot_id)
        if sync_activity:
            self.refresh_activity_feed()
        self._render_activity_agent_list(get_all_bots())

    def _highlight_selected_agent(self, bot_id: int):
        for current_id, card in self.agent_cards.items():
            selected = current_id == bot_id
            card.configure(
                fg_color=CARD_ALT if selected else CARD_BG,
                border_color=PRIMARY if selected else BORDER,
                border_width=1 if not selected else 2,
            )

    def _render_selected_agent(self, cfg):
        if not cfg:
            self.selected_emblem.configure(text="☾")
            self.selected_name.configure(text="No agent selected")
            self.selected_meta.configure(text="Choose an agent from the left to inspect its status and controls.")
            for label in self.info_labels.values():
                label.configure(text="--")
            self.launch_button.configure(text="Launch", fg_color=SUCCESS, hover_color="#91E7CB")
            self._set_textbox(self.prompt_preview, "")
            self._set_textbox(self.recent_activity_box, "No events yet.")
            self._set_agent_action_state(False)
            return

        bot_id = cfg["id"]
        running = self.manager.is_running(bot_id)
        uptime = self.manager.get_uptime(bot_id)
        trigger = cfg.get("trigger_prefix") or "All direct messages"

        self.selected_emblem.configure(text=cfg.get("emoji") or "☾")
        self.selected_name.configure(text=cfg["name"])
        self.selected_meta.configure(
            text=f"{('Online' if running else 'Standby')}  ·  Uptime {uptime}  ·  Phone {cfg.get('phone', '--')}",
        )
        self.info_labels["model"].configure(text=cfg.get("claude_model") or "--")
        self.info_labels["trigger"].configure(text=trigger)
        self.info_labels["timezone"].configure(text=cfg.get("timezone") or "--")
        self.launch_button.configure(
            text="Stop" if running else "Launch",
            fg_color=DANGER if running else SUCCESS,
            hover_color="#F7ACB4" if running else "#91E7CB",
        )
        self._set_agent_action_state(True)

        self._set_textbox(self.prompt_preview, cfg.get("system_prompt", ""))
        self._set_textbox(self.recent_activity_box, self._format_logs_text(get_logs(bot_id, limit=8)))

    def _set_agent_action_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.launch_button.configure(state=state)
        self.edit_button.configure(state=state)
        self.session_button.configure(state=state)
        self.delete_button.configure(state=state)

    def start_create_agent(self):
        self.current_agents_mode = "form"
        self.agent_form_view.load_create_defaults()
        self.agent_detail_view.grid_remove()
        self.agent_form_view.grid()

    def start_edit_selected_agent(self):
        if self.selected_bot_id is None:
            messagebox.showinfo("No agent selected", "Select an agent before editing it.")
            return
        self.current_agents_mode = "form"
        self.agent_form_view.load_bot(self.selected_bot_id)
        self.agent_detail_view.grid_remove()
        self.agent_form_view.grid()

    def exit_agent_form(self):
        self.current_agents_mode = "overview"
        self.agent_form_view.grid_remove()
        self.agent_detail_view.grid()
        if self.selected_bot_id is not None:
            self._render_selected_agent(get_bot(self.selected_bot_id))
    def save_agent(self, bot_id, payload):
        if bot_id is None:
            new_id = add_bot(**payload)
            self.manager.refresh_bot(new_id)
            self.refresh_all_views(keep_selection=False)
            self.select_bot(new_id)
        else:
            was_running = self.manager.is_running(bot_id)
            if was_running:
                self.manager.stop_bot(bot_id)
            update_bot(bot_id, **payload)
            self.manager.refresh_bot(bot_id)
            if was_running:
                self.manager.start_bot(bot_id)
            self.refresh_all_views()
            self.select_bot(bot_id)
        self.exit_agent_form()

    def toggle_selected_bot(self):
        if self.selected_bot_id is None:
            return
        if self.manager.is_running(self.selected_bot_id):
            self.manager.stop_bot(self.selected_bot_id)
        else:
            self.manager.start_bot(self.selected_bot_id)
        self.refresh_all_views()
        self.select_bot(self.selected_bot_id)

    def create_session_for_selected(self):
        if self.selected_bot_id is None:
            return
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "create_session.py")
        bot_id = str(self.selected_bot_id)
        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    ["cmd", "/c", "start", "cmd", "/k", sys.executable, script, "--bot-id", bot_id],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(["x-terminal-emulator", "-e", sys.executable, script, "--bot-id", bot_id])
        except Exception as exc:
            messagebox.showerror("Unable to open terminal", f"Could not open a new terminal window.\n\n{exc}\n\nRun manually:\npython create_session.py --bot-id {bot_id}")

    def delete_selected_agent(self):
        if self.selected_bot_id is None:
            return
        cfg = get_bot(self.selected_bot_id)
        if not cfg:
            return
        if not messagebox.askyesno("Delete agent", f"Delete {cfg['name']} and all of its logs?"):
            return
        self.manager.remove_bot(self.selected_bot_id)
        delete_bot(self.selected_bot_id)
        self.selected_bot_id = None
        self.refresh_all_views(keep_selection=False)

    def refresh_analytics_page(self, bots=None):
        bots = bots if bots is not None else get_all_bots()
        for widget in self.analytics_list.winfo_children():
            widget.destroy()

        totals = {"messages": 0, "tokens": 0}
        active = 0
        for cfg in bots:
            if self.manager.is_running(cfg["id"]):
                active += 1
            rows = list(reversed(get_stats(cfg["id"])))
            totals_row = get_total_stats(cfg["id"])
            totals["messages"] += sum(row["messages_count"] for row in rows)
            totals["tokens"] += sum(row["tokens_total"] for row in rows)

            card = SectionCard(self.analytics_list, f"{cfg.get('emoji') or '☾'}  {cfg['name']}", f"{cfg.get('claude_model')} · {cfg.get('timezone')}")
            card.pack(fill="x", pady=8)
            summary = ctk.CTkFrame(card.body, fg_color=CARD_BG)
            summary.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(summary, text=f"7d messages: {sum(row['messages_count'] for row in rows)}", text_color=TEXT, font=("Segoe UI Semibold", 13)).pack(side="left")
            ctk.CTkLabel(summary, text=f"Lifetime tokens: {totals_row['total_tokens']}", text_color=TEXT_SOFT, font=("Segoe UI", 11)).pack(side="right")

            if not rows:
                ctk.CTkLabel(card.body, text="No analytics yet.", text_color=TEXT_SOFT, font=("Segoe UI", 12)).pack(anchor="w")
                continue

            max_messages = max(row["messages_count"] for row in rows) or 1
            max_tokens = max(row["tokens_total"] for row in rows) or 1
            for row in rows:
                item = ctk.CTkFrame(card.body, fg_color=CARD_BG)
                item.pack(fill="x", pady=4)
                ctk.CTkLabel(item, text=row["date"], width=96, anchor="w", text_color=TEXT_MUTED, font=("Segoe UI", 11)).pack(side="left")
                msg_bar = ctk.CTkProgressBar(item, width=170, height=10, progress_color=PRIMARY, fg_color=SURFACE_BG)
                msg_bar.pack(side="left", padx=(0, 10))
                msg_bar.set(row["messages_count"] / max_messages if max_messages else 0)
                ctk.CTkLabel(item, text=f"{row['messages_count']} msgs", width=78, anchor="w", text_color=TEXT, font=("Segoe UI", 11)).pack(side="left")
                tok_bar = ctk.CTkProgressBar(item, width=170, height=10, progress_color=SECONDARY, fg_color=SURFACE_BG)
                tok_bar.pack(side="left", padx=(12, 10))
                tok_bar.set(row["tokens_total"] / max_tokens if max_tokens else 0)
                ctk.CTkLabel(item, text=f"{row['tokens_total']} tok", width=90, anchor="w", text_color=TEXT_SOFT, font=("Segoe UI", 11)).pack(side="left")

        self._update_metric_card(self.analytics_metric_cards["agents"], str(len(bots)), "Total configured identities", PRIMARY)
        self._update_metric_card(self.analytics_metric_cards["active"], str(active), "Agents currently launched", SUCCESS)
        self._update_metric_card(self.analytics_metric_cards["messages"], str(totals["messages"]), "Messages counted over the last 7 days", WARNING)
        self._update_metric_card(self.analytics_metric_cards["tokens"], str(totals["tokens"]), "Tokens counted over the last 7 days", SECONDARY)

    def _update_metric_card(self, card: MetricCard, value: str, detail: str, accent: str):
        labels = card.winfo_children()
        labels[1].configure(text=value)
        labels[2].configure(text=detail, text_color=accent)

    def refresh_activity_feed(self):
        if self.selected_bot_id is None:
            self._clear_activity_console("Select an agent to inspect its activity feed.")
            self.activity_title.configure(text="No agent selected")
            return
        cfg = get_bot(self.selected_bot_id)
        if not cfg:
            return
        self.activity_title.configure(text=f"{cfg.get('emoji') or '☾'}  {cfg['name']}")
        self._clear_activity_console(self._format_logs_text(get_logs(self.selected_bot_id, limit=200)))

    def clear_selected_logs(self):
        if self.selected_bot_id is None:
            return
        cfg = get_bot(self.selected_bot_id)
        if not cfg:
            return
        if not messagebox.askyesno("Clear logs", f"Clear all saved logs for {cfg['name']}?"):
            return
        clear_logs(self.selected_bot_id)
        self.refresh_activity_feed()
        self._render_selected_agent(cfg)

    def refresh_system_page(self, bots=None):
        bots = bots if bots is not None else get_all_bots()
        active = sum(1 for cfg in bots if self.manager.is_running(cfg["id"]))
        lines = [
            f"version: {CURRENT_VERSION}",
            f"configured_agents: {len(bots)}",
            f"active_agents: {active}",
            f"selected_agent: {self.selected_bot_id if self.selected_bot_id is not None else 'none'}",
            "workspace_mode: single-window",
            "product_focus: telegram-userbot-management",
        ]
        self._set_textbox(self.system_runtime_box, "\n".join(lines))

    def _format_logs_text(self, entries):
        if not entries:
            return "No activity recorded yet."
        lines = []
        for entry in entries:
            direction = entry.get("direction")
            arrow = "→" if direction == "out" else "←" if direction == "in" else "•"
            label = entry.get("chat_name") or "Unknown"
            tokens = entry.get("tokens_used") or entry.get("tokens") or 0
            token_suffix = f" [{tokens}t]" if tokens else ""
            message = (entry.get("message") or "").strip()
            lines.append(f"[{short_time(entry.get('timestamp', ''))}] {arrow} {label}{token_suffix}\n  {message}")
        return "\n\n".join(lines)

    def _set_textbox(self, widget: ctk.CTkTextbox, text: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _clear_activity_console(self, text: str):
        self._set_textbox(self.activity_console, text)

    def _handle_log(self, bot_id: int, entry: dict):
        self.live_logs.setdefault(bot_id, []).append(entry)
        if self.selected_bot_id == bot_id:
            current = self.activity_console.get("1.0", "end").strip()
            snippet = self._format_logs_text([entry])
            next_text = f"{snippet}\n\n{current}" if current and current != "No activity recorded yet." else snippet
            self._clear_activity_console(next_text)
            combined = get_logs(bot_id, limit=7) + [entry]
            self._set_textbox(self.recent_activity_box, self._format_logs_text(combined[-8:]))

    def _on_log(self, bot_id: int, entry: dict):
        if not self.winfo_exists():
            return
        self.after(0, lambda: self._handle_log(bot_id, entry) if self.winfo_exists() else None)

    def _on_bot_state(self, bot_id: int, state: str, details: dict | None = None):
        if not self.winfo_exists():
            return
        self.after(0, lambda: self._handle_bot_state(bot_id, state, details or {}) if self.winfo_exists() else None)

    def _handle_bot_state(self, bot_id: int, state: str, details: dict):
        bots = get_all_bots()
        self._render_agent_list(bots)
        self._render_activity_agent_list(bots)
        self._update_sidebar_metrics(bots)
        self.refresh_analytics_page(bots)
        self.refresh_system_page(bots)
        if self.selected_bot_id == bot_id:
            cfg = get_bot(bot_id)
            self._render_selected_agent(cfg)
            if state == "error" and details.get("message"):
                self.selected_meta.configure(text=f"Start failed  ·  {details['message']}")

    def _on_close(self):
        self.manager.stop_all()
        self.destroy()


if __name__ == "__main__":
    app = SeleneApp()
    app.mainloop()
