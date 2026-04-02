---
title: Overview
section: 02-api-reference
order: 1
generated: 2026-04-02T16:08:43.998607
---
# API Overview

This section documents the available API endpoints and tools.




## Classes


### `CheckResult`

Result of running a loop check.




### `Notifier`

Routes notifications to file, webhook, or stderr.


**Methods:**

| Method | Description |
|--------|-------------|
| `__init__` |  |
| `notify` | Send notification for a loop event. |



### `SchedulerThread`

Background daemon thread that polls the store and fires checks. Runs every `poll_interval` seconds, finds active loops with nextCheckAt <= now, and runs their checks. Handles retry, backoff, expiry, and recovery on startup.


**Methods:**

| Method | Description |
|--------|-------------|
| `__init__` |  |
| `run` | Main loop — poll and fire until stopped. |
| `stop` | Signal the scheduler to stop. |



### `LoopStore`

Manages loop entries as JSON files with fcntl locking for thread safety.


**Methods:**

| Method | Description |
|--------|-------------|
| `__init__` |  |
| `create` | Create a new loop entry (thread-safe). |
| `get` | Read a loop entry (no lock needed — atomic writes). |
| `update` | Merge updates into existing entry (thread-safe). |
| `delete` | Delete a loop entry (thread-safe). |
| `list_all` | List all entries, optionally filtered by status. |
| `add_history` | Add history entry and increment attempt (thread-safe). |
| `set_status` | Update loop status (thread-safe). |
| `set_next_check` | Update the next check time (thread-safe). |






## Functions

| Function | Description |
|----------|-------------|
| `run_check(check_type: str, command: str, success_criteria: str) -> CheckResult` | Execute a check and return the result. |
| `cmd_list(args)` |  |
| `cmd_show(args)` |  |
| `cmd_dashboard(args)` |  |
| `cmd_history(args)` |  |
| `cmd_cancel(args)` |  |
| `cmd_batch(args)` |  |
| `cmd_stats(args)` |  |
| `cmd_notifications(args)` | Query notification history from JSONL files. |
| `main(argv)` |  |
| `loop_schedule(task: str, check_command: str, check_type: str, success_criteria: str, context_why: str, context_started_by: str, related_files: str, check_after_minutes: int, max_retries: int, retry_backoff_minutes: str, expires_after_hours: int, notify_method: str, webhook_url: str, slack_webhook_url: str, telegram_bot_token: str, telegram_chat_id: str, discord_webhook_url: str, teams_webhook_url: str, ntfy_server: str, ntfy_topic: str, pushover_user_key: str, pushover_app_token: str, gotify_server_url: str, gotify_app_token: str, matrix_homeserver: str, matrix_access_token: str, matrix_room_id: str, twilio_account_sid: str, twilio_auth_token: str, twilio_from_number: str, twilio_to_number: str, google_chat_webhook_url: str, smtp_server: str, smtp_port: int, smtp_username: str, smtp_password: str, smtp_from: str, smtp_to: str, smtp_use_tls: bool) -> str` | Schedule a self-managed follow-up check. No external scheduler needed. |
| `loop_check(loop_id: str) -> str` | Manually trigger a check for a loop (bypasses scheduler timing). |
| `loop_list(status: str) -> str` | List all loops, optionally filtered by status. |
| `loop_cancel(loop_id: str) -> str` | Cancel an active loop. |
| `loop_history(status: str, keyword: str, limit: int) -> str` | View past loops with stats. |
| `loop_schedule_template(template: str, target: str, check_after_minutes: int, max_retries: int, context_why: str) -> str` | Schedule using a pre-defined template. |
| `loop_dashboard() -> str` | Formatted overview of all loops — active + recent. |
| `loop_batch(action: str) -> str` | Batch operations: cancel_expired, retry_failed, cleanup_done, summary. |
| `loop_write_result(loop_id: str, file_path: str) -> str` | Write a loop's result to a file (markdown format). |
| `main()` | Run the Gen-Loop MCP server with internal scheduler. |
| `apply_template(template_name: str, target: str) -> dict[str, Any]` | Apply a template with the given target, returning loop_schedule kwargs. |

---

## See Also

- [Getting Started](../01-user-guide/01-getting-started.md)
- [Installation](../01-user-guide/02-installation.md)
- [Quick Start](../01-user-guide/03-quick-start.md)
- [Worked Examples](../01-user-guide/04-worked-examples.md)
- [System Overview](../03-architecture/01-system-overview.md)