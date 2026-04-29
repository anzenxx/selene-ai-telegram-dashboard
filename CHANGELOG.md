# Changelog

## Unreleased

- No unreleased changes yet.

## v1.0.0 - 2026-04-29

### Added
- Per-chat dialogue runtime in `core/userbot.py` with separate state for each `chat_id`.
- Thought grouping for bursts of user messages, so short consecutive messages are treated as one user turn.
- Intent resolution before reply generation: `question`, `emotion`, `story`, `presence_check`, `small_talk`, `multi_topic`.
- Anti-topic-drift prompt rules to keep the model focused on the current dominant user thread.
- Global workspace prompt defaults in `core/prompt_defaults.py`, applied automatically on top of individual agent prompts.
- Agent style profiles in `core/prompt_defaults.py`, giving each default userbot role its own tone, pacing, message shape, and initiative style.
- Layered conversation memory with `stable_facts`, `recent_context`, and `emotional_cues`, while keeping old flat memory records backward-compatible.
- Situational `reply-to` support for private chats, using stored incoming `message_id`s and activating only in contexts where anchoring the answer improves readability.

### Changed
- Replaced the old `cold / warm / active` timing logic with a per-chat state machine: `new_contact`, `reopening`, `warming_up`, `engaged`, `cooldown`, `silent`.
- Replaced the rigid "ignore every 17th message" mechanic with probabilistic ignore logic based on chat state and intent.
- Reworked reply timing, typing cadence, and multipart behavior to depend on the current per-chat state and detected user intent.
- Replaced primitive buffer concatenation through `" | "` with grouped structured user turns.
- Incoming private messages are now marked as read when the agent receives them.
- Reply post-processing now normalizes output into shorter separate messages, removes emoji by default, and replaces long dashes.
- Explicit `|||` split markers are now forced into separate outgoing messages so delimiters never leak into Telegram replies.
- Removed artificial standalone `"..."` bridge messages and tightened prompt rules so self-description sounds more like live chat and less like a resume.
- Embedded the shared workspace skeleton prompt into the app runtime, so each agent now inherits one common behavioral layer without losing its own individual prompt.
- Incoming messages are no longer marked as read immediately; the agent now comes online and reads the chat shortly before typing the reply.
- Fixed a bypass in prefix-trigger mode so replies there also go through the same split/filter pipeline and no longer leak `|||` into chat.
- Added lightweight sticker-only handling: short contextual reactions, faster timing, and no Claude call for pure sticker turns.
- Updated the GUI theme to an `Ash Violet Night` palette and reduced black flicker by replacing several transparent containers with solid surfaces and switching page changes to `tkraise()`.
- Refined the GUI page stack again: pages now share a single `grid` cell and are raised in-place, which fixes incorrect sidebar tab switching and removes another source of black flicker during page changes.
- Replaced the remaining transparent analytics subframes with solid card surfaces to reduce transient black blocks during resize, minimize/restore, and tab switches.
- Tightened page switching logic so only the selected page is shown at a time, preventing stale Agents/Activity content from appearing on Analytics, System, or Release Notes.
- Refactored Claude prompt assembly in `core/userbot.py` into explicit layers: workspace rules, role prompt, style profile, memory, runtime context, and behavioral rules.
- Added a reply style pass that can reshape long parts differently per agent before messages are sent.
- Added a basic anti-repetition pass that trims repeated openers and drops near-duplicate outgoing lines compared with the bot's recent replies.
- Reworked memory extraction so Claude now returns structured memory layers instead of a flat fact dict, and existing memory records are normalized automatically on read/save.
- Updated the prompt memory block so the model separately sees stable facts, recent user context, and emotional markers instead of one mixed list of facts.
- Added selective reply targeting so the first outgoing part can answer a specific incoming message in question-heavy or multi-topic turns, instead of using reply-to on every message.

### Behavioral Notes
- The agent is now less likely to answer across multiple stale threads at once.
- The agent is now less likely to continue her own previous line instead of responding to the latest user turn.
- Active chats should feel faster and more coherent, while long-paused chats should feel slower without the old abrupt cold-start behavior.

### Roadmap
- V1: prompt assembly cleanup, agent style profiles, anti-repetition baseline.
- V2: stronger memory layers, situational reply-to, and richer media behavior.
- V3: prompt preview/debug tooling and behavioral quality metrics inside Selene.
