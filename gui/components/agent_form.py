import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from core.prompts import DEFAULT_AGENT_PROMPTS
from db.database import get_bot
from gui.components.cards import SectionCard
from gui.theme import AGENT_EMBLEMS, APP_BG, BORDER, CARD_ALT, CARD_BG, CARD_HOVER, CLAUDE_MODELS, PRIMARY, PRIMARY_HOVER, SURFACE_BG, TEXT, TEXT_MUTED, TEXT_SOFT, TIMEZONES


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
        kwargs = {"height": 40, "corner_radius": 12, "fg_color": SURFACE_BG, "border_color": BORDER, "text_color": TEXT, "font": ("Segoe UI", 12), "placeholder_text": placeholder}
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
        return ctk.CTkComboBox(parent, **kwargs)

    def _build(self):
        top = ctk.CTkFrame(self, fg_color=APP_BG)
        top.pack(fill="x", pady=(2, 14))
        title_row = ctk.CTkFrame(top, fg_color=APP_BG)
        title_row.pack(fill="x")
        self.title_label = ctk.CTkLabel(title_row, text="Create Agent", font=("Segoe UI Semibold", 24), text_color=TEXT)
        self.title_label.pack(side="left", anchor="w")
        ctk.CTkButton(title_row, text="Back", width=86, height=34, corner_radius=12, fg_color=CARD_ALT, hover_color=CARD_HOVER, text_color=TEXT, command=self.on_cancel).pack(side="right")
        self.subtitle_label = ctk.CTkLabel(top, text="Configure a Telegram userbot profile, credentials, and response behavior.", font=("Segoe UI", 12), text_color=TEXT_SOFT)
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
        self.name_combo = self._combo(name_box, list(DEFAULT_AGENT_PROMPTS.keys()), self.name_var, command=self._on_name_change)
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
        ctk.CTkButton(tz_row, text="Add", width=74, height=40, corner_radius=12, fg_color=CARD_ALT, hover_color=CARD_HOVER, text_color=TEXT, command=self._add_timezone).grid(row=0, column=1)

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
        self.prompt_text = ctk.CTkTextbox(behavior.body, height=210, fg_color=SURFACE_BG, border_color=BORDER, border_width=1, text_color=TEXT, font=("Segoe UI", 12), corner_radius=14)
        self.prompt_text.pack(fill="x")

        footer = ctk.CTkFrame(self, fg_color=APP_BG)
        footer.pack(fill="x", pady=(14, 10))
        ctk.CTkButton(footer, text="Cancel", width=110, height=42, corner_radius=14, fg_color=CARD_ALT, hover_color=CARD_HOVER, text_color=TEXT, command=self.on_cancel).pack(side="left")
        self.save_button = ctk.CTkButton(footer, text="Save Agent", width=140, height=42, corner_radius=14, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color=APP_BG, font=("Segoe UI Semibold", 12), command=self._submit)
        self.save_button.pack(side="right")

    def _clear_entries(self):
        for entry in [self.api_id_entry, self.api_hash_entry, self.phone_entry, self.anthropic_entry, self.max_tokens_entry, self.trigger_entry]:
            entry.delete(0, "end")
        self.prompt_text.delete("1.0", "end")

    def load_create_defaults(self):
        self.mode = "create"
        self.edit_bot_id = None
        self.title_label.configure(text="Create Agent")
        self.subtitle_label.configure(text="Configure a Telegram userbot profile, credentials, and response behavior.")
        self.save_button.configure(text="Save Agent")
        self._clear_entries()
        self.name_var.set(list(DEFAULT_AGENT_PROMPTS.keys())[0])
        self.emblem_var.set(AGENT_EMBLEMS[0])
        self.model_var.set(CLAUDE_MODELS[0])
        self.timezone_var.set(TIMEZONES[0])
        self.max_tokens_entry.insert(0, "512")
        self.trigger_entry.insert(0, ".ai")
        self.prompt_text.insert("1.0", DEFAULT_AGENT_PROMPTS[self.name_var.get()])

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
        self.name_var.set((cfg.get("name") or list(DEFAULT_AGENT_PROMPTS.keys())[0]).upper())
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
            self.prompt_text.insert("1.0", DEFAULT_AGENT_PROMPTS.get(value, ""))

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
        payload = dict(name=name, emoji=emoji, api_id=api_id, api_hash=api_hash, phone=phone, anthropic_key=anthropic_key, claude_model=model, system_prompt=prompt, trigger_prefix=trigger_prefix, max_tokens=max_tokens, timezone=timezone)
        self.on_save(self.edit_bot_id, payload)
