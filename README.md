<p align="center">
  <img src="gui/assets/selene.png" alt="Selene logo" width="180" />
</p>

<h1 align="center">Selene</h1>

<p align="center">
  <strong>Local desktop dashboard for managing AI-assisted Telegram accounts</strong>
</p>

<p align="center">
  <a href="#english">English</a> |
  <a href="#deutsch">Deutsch</a> |
  <a href="#русский">Русский</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-2F6F9F?style=flat-square" alt="CustomTkinter" />
  <img src="https://img.shields.io/badge/SQLite-local-3F7F5F?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/Telethon-Telegram-229ED9?style=flat-square&logo=telegram&logoColor=white" alt="Telethon" />
  <img src="https://img.shields.io/badge/Claude-Anthropic-6B5B95?style=flat-square" alt="Anthropic Claude" />
  <img src="https://img.shields.io/badge/version-v1.0.0-B6A7E8?style=flat-square" alt="Version v1.0.0" />
  <img src="https://img.shields.io/badge/license-MIT-6AA84F?style=flat-square" alt="MIT license" />
</p>

Selene is a Python desktop application for configuring, launching, and monitoring multiple AI-assisted Telegram automation profiles. It combines Telethon sessions, Anthropic Claude prompts, local SQLite persistence, runtime controls, activity logs, and basic analytics in a single CustomTkinter workspace.

Created by Artem Silenko.

---

## Highlights

- Manage multiple Telegram automation profiles from one desktop UI.
- Configure Telegram API credentials, phone number, timezone, trigger prefix, Claude model, and system prompt per profile.
- Start and stop profiles without leaving the main workspace.
- Keep local logs for incoming/outgoing messages and token usage.
- Track seven-day activity and token statistics.
- Use neutral default roles: `SUPPORT`, `SALES`, `RESEARCH`, `OPS`, `COMMUNITY`, `WRITER`.
- Store local conversational memory per chat for more contextual replies.

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop UI | CustomTkinter |
| Language | Python |
| Messaging | Telethon |
| AI provider | Anthropic Claude API |
| Storage | SQLite |
| Assets | Pillow |

## Project Structure

```text
Selene/
├── main.py              # Application entry point
├── requirements.txt
├── gui/
│   ├── workspace.py     # Main CustomTkinter workspace
│   ├── theme.py         # Shared UI constants
│   └── components/      # Reusable UI components
├── core/
│   ├── userbot.py       # Telethon runtime and Claude integration
│   ├── bot_manager.py   # Multi-profile lifecycle manager
│   ├── prompts/         # Prompt assembly and default roles
│   └── behavior/        # Reply timing and post-processing
├── db/
│   └── database.py      # SQLite schema initialization and repository facade
└── sessions/            # Local Telethon session files, ignored by Git
```

## Installation

```bash
pip install -r requirements.txt
```

You will need:

- Telegram API ID and API Hash from [my.telegram.org/apps](https://my.telegram.org/apps)
- Anthropic API key from [console.anthropic.com](https://console.anthropic.com)

Use `.env.example` as a reference for required credentials. Real credentials are entered in the app UI and must not be committed.

## Run

```bash
python main.py
```

Current release: `v1.0.0`.

## Add a Profile

1. Open the app and click **Create Agent**.
2. Choose a role preset or enter a custom profile name.
3. Fill in Telegram API ID, API Hash, and phone number.
4. Add an Anthropic API key and choose a Claude model.
5. Adjust the trigger prefix and system prompt.
6. Save the profile and start it from the workspace.

On first login, Telethon may request a Telegram confirmation code in the terminal. The resulting session is saved locally in `sessions/`.

## Usage

By default, the assistant responds when a message starts with the configured trigger prefix:

```text
.ai Summarize the last discussion and suggest next steps.
```

If the trigger prefix is empty, the runtime can respond to all private messages handled by the profile.

## Local Data and Safety

- SQLite data is stored locally in `db/selene.db`.
- Telethon session files are stored locally in `sessions/`.
- `.env`, SQLite databases, session files, and build artifacts are ignored by Git.
- Use a separate Telegram account for testing and respect Telegram platform rules and rate limits.

## English

Selene is a local Python desktop dashboard for managing AI-assisted Telegram automation profiles with local storage, logs, analytics, and configurable Claude prompts.

## Deutsch

Selene ist eine lokale Python-Desktop-App zur Verwaltung von KI-unterstuetzten Telegram-Automatisierungsprofilen mit lokaler Speicherung, Logs, Analysen und konfigurierbaren Claude-Prompts.

## Русский

Selene - локальное desktop-приложение на Python для управления AI-assisted Telegram-профилями с локальной базой данных, логами, аналитикой и настраиваемыми Claude-промптами.

## License

MIT
