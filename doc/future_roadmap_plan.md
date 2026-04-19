# Implementation Plan: Telegram Channel Pillar

This plan outlines the architectural expansion of the OpenClaw system to support cross-platform communication via the Telegram Channel Pillar.

## User Review Required

> [!IMPORTANT]
> **Telegram Identity Linking**: The system currently uses `phone_number` as the unique user ID. We need a secure way to link a Telegram `chat_id` to this ID. I propose using a "Sync Code" generated in the Dashboard that the user sends to the Telegram Bot.

## Proposed Changes

---

### 📡 Phase 1: Telegram Channel Pillar

#### [NEW] [telegram_client.py](file:///c:/openClaw/app/channels/telegram/client.py)
- Implement `TelegramClient` using `python-telegram-bot`.
- Handle `/start`, `/help`, and `/sync <code>` commands.
- Support sending text and (later) architectural diagrams.

#### [MODIFY] [scheduler.py](file:///c:/openClaw/app/services/scheduler.py)
- Refactor delivery logic to be channel-agnostic.
- Iterate through enabled channels (WhatsApp, Telegram) defined in `user_configs`.

#### [MODIFY] [dashboard.py](file:///c:/openClaw/dashboard.py)
- Add "Telegram Settings" section.
- Display "Sync Code" for bot linking.
- Field to input custom Bot Token (optional) or use a global one.

## Verification Plan

### Automated Tests
- `pytest tests/test_telegram.py`: Verify message dispatching and command handling.

### Manual Verification
1. Register via Dashboard.
2. Link Telegram Bot via sync code.
3. Receive a daily challenge on BOTH WhatsApp and Telegram.
