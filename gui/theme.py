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

CURRENT_VERSION = "v1.0.0"
RELEASE_NOTES = [
    {
        "version": "v1.0.0",
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
