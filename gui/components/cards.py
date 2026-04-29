import customtkinter as ctk

from gui.theme import BORDER, CARD_BG, TEXT, TEXT_SOFT


def short_time(value: str) -> str:
    return value[-8:] if value and len(value) >= 8 else value or "--:--:--"


class SectionCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, subtitle: str | None = None):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=20, border_width=1, border_color=BORDER)
        header = ctk.CTkFrame(self, fg_color=CARD_BG)
        header.pack(fill="x", padx=18, pady=(16, 12))
        ctk.CTkLabel(header, text=title, font=("Segoe UI Semibold", 16), text_color=TEXT, anchor="w").pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(header, text=subtitle, font=("Segoe UI", 11), text_color=TEXT_SOFT, anchor="w").pack(anchor="w", pady=(3, 0))
        self.body = ctk.CTkFrame(self, fg_color=CARD_BG)
        self.body.pack(fill="both", expand=True, padx=18, pady=(0, 18))


class MetricCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str, detail: str, accent: str):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=18, border_width=1, border_color=BORDER)
        ctk.CTkLabel(self, text=title, text_color=TEXT_SOFT, font=("Segoe UI", 11)).pack(anchor="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(self, text=value, text_color=TEXT, font=("Segoe UI Semibold", 24)).pack(anchor="w", padx=16)
        ctk.CTkLabel(self, text=detail, text_color=accent, font=("Segoe UI", 11)).pack(anchor="w", padx=16, pady=(6, 14))
