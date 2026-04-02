---
title: Data Models
section: 03-architecture
order: 2
generated: 2026-04-02T16:08:44.035687
---
# Data Models

Key data structures and models used in the project.


## Classes from Check type implementations — identical to loop-mcp, zero external deps.

### `CheckResult`

Result of running a loop check.



## Classes from Notification delivery — file, webhook, Slack, Telegram, Discord, Teams, ntfy, Pushover, Gotify, Matrix, Twilio SMS, Google Chat, email, stderr.

### `Notifier`

Routes notifications to file, webhook, or stderr.

**Methods:**

- `__init__(self, store_dir: str | Path, default_method: str)`
- `notify(self, entry: dict[str, Any], event_type: str, check_result: Any)`
  - Send notification for a loop event.


## Classes from Internal scheduler thread — polls store and fires checks autonomously.

### `SchedulerThread`

Background daemon thread that polls the store and fires checks.

Runs every `poll_interval` seconds, finds active loops with
nextCheckAt <= now, and runs their checks. Handles retry, backoff,
expiry, and recovery on startup.

**Methods:**

- `__init__(self, store: LoopStore, poll_interval: float, on_event: callable, max_concurrent: int)`
- `run(self)`
  - Main loop — poll and fire until stopped.
- `stop(self)`
  - Signal the scheduler to stop.


## Classes from Thread-safe file-based JSON store for loop entries.

### `LoopStore`

Manages loop entries as JSON files with fcntl locking for thread safety.

**Methods:**

- `__init__(self, store_dir: str | Path)`
- `create(self, task: str, check_type: str, check_command: str, success_criteria: str, context: dict[str, Any] | None, check_after_minutes: int, max_retries: int, retry_backoff_minutes: list[int] | None, expires_after_hours: int, notify_method: str, webhook_url: str, slack_webhook_url: str, telegram_bot_token: str, telegram_chat_id: str, discord_webhook_url: str, teams_webhook_url: str, ntfy_server: str, ntfy_topic: str, pushover_user_key: str, pushover_app_token: str, gotify_server_url: str, gotify_app_token: str, matrix_homeserver: str, matrix_access_token: str, matrix_room_id: str, twilio_account_sid: str, twilio_auth_token: str, twilio_from_number: str, twilio_to_number: str, google_chat_webhook_url: str, smtp_server: str, smtp_port: int, smtp_username: str, smtp_password: str, smtp_from: str, smtp_to: str, smtp_use_tls: bool) -> dict[str, Any]`
  - Create a new loop entry (thread-safe).
- `get(self, loop_id: str) -> dict[str, Any] | None`
  - Read a loop entry (no lock needed — atomic writes).
- `update(self, loop_id: str, updates: dict[str, Any]) -> dict[str, Any] | None`
  - Merge updates into existing entry (thread-safe).
- `delete(self, loop_id: str) -> bool`
  - Delete a loop entry (thread-safe).
- `list_all(self, status: str | None) -> list[dict[str, Any]]`
  - List all entries, optionally filtered by status.
- `add_history(self, loop_id: str, result: str, output: str, note: str) -> dict[str, Any] | None`
  - Add history entry and increment attempt (thread-safe).
- `set_status(self, loop_id: str, status: str) -> dict[str, Any] | None`
  - Update loop status (thread-safe).
- `set_next_check(self, loop_id: str, next_check_at: str) -> dict[str, Any] | None`
  - Update the next check time (thread-safe).

---

## See Also

- [Getting Started](../01-user-guide/01-getting-started.md)
- [Installation](../01-user-guide/02-installation.md)
- [Quick Start](../01-user-guide/03-quick-start.md)
- [Worked Examples](../01-user-guide/04-worked-examples.md)
- [Overview](../02-api-reference/01-overview.md)

---

Previous: [System Overview](01-system-overview.md)