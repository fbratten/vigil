---
title: Changelog
section: 05-appendix
order: 3
generated: 2026-04-02T16:08:44.116665
---
# Changelog

Track of changes and version history for this project.


## Recent Changes

See project commit history for recent changes.



## Version History

## [0.15.0] — Notification History CLI (2026-02-05)

### Added
- **CLI `notifications` subcommand** — query notification history from JSONL files
- Filter by: `--loop-id`, `--event` (completed/failed/expired/retry/cancelled), `--since`, `--until`
- `--limit N` to cap results (default: 50)
- `--include-rotated` to read from rotated `.jsonl.1` file
- `--json` output mode for scripting/automation
- Tabular output: TIME, LOOP, EVENT, STATUS, TASK columns
- Graceful handling of missing files and malformed JSON lines
- 12 new tests (148 total): all filter combinations, JSON output, rotated file handling

### Changed
- CLI subcommand count: 7 → 8

## [0.14.0] — Google Chat Notifications (2026-02-02)

### Added
- **Google Chat notifications** — "google_chat" as a first-class notification method
- POST JSON Cards v2 to Google Chat Incoming Webhook URL — auth entirely in URL (key + token params)
- Cards v2 formatting: header with emoji + status, decorated text widgets (Task, Status, Attempts), collapsible output section, footer
- `GEN_LOOP_GOOGLE_CHAT_WEBHOOK_URL` env var
- `google_chat_webhook_url` parameter on `loop_schedule` tool
- `googleChatWebhookUrl` field in loop entry notification object
- Reuses `_notify_webhook()` retry logic (same as Slack, Discord, Teams, ntfy, Pushover, Gotify)
- "all" method now sends to file + webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + twilio_sms + google_chat + email (when configured)
- Fallback to file on Google Chat failure (marked `_google_chat_fallback: true`)
- 6 new tests (136 total): Google Chat card structure, collapsible output, retry/fallback, all-method integration

## [0.13.0] — Twilio SMS Notifications (2026-02-02)

### Added
- **Twilio SMS notifications** — "twilio_sms" as a first-class notification method
- POST form-encoded to `https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages` — HTTP Basic auth (`base64(SID:Token)`)
- Plain-text SMS body with emoji status, loop details, optional output (truncated 100 chars)
- `GEN_LOOP_TWILIO_ACCOUNT_SID`, `GEN_LOOP_TWILIO_AUTH_TOKEN`, `GEN_LOOP_TWILIO_FROM_NUMBER`, `GEN_LOOP_TWILIO_TO_NUMBER` env vars
- `twilio_account_sid`, `twilio_auth_token`, `twilio_from_number`, `twilio_to_number` parameters on `loop_schedule` tool
- `twilioAccountSid`, `twilioAuthToken`, `twilioFromNumber`, `twilioToNumber` fields in loop entry notification object
- Own retry logic (3 attempts, 0/1/2s backoff) — Twilio requires form-encoded + Basic auth, cannot reuse `_notify_webhook()`
- "all" method now sends to file + webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + twilio_sms + email (when configured)
- Fallback to file on Twilio SMS failure (marked `_twilio_sms_fallback: true`)
- 6 new tests (130 total): Twilio SMS success, message structure, Basic auth verification, retry/fallback, all-method integration

## [0.12.0] — Matrix Notifications (2026-02-02)

### Added
- **Matrix notifications** — "matrix" as a first-class notification method
- PUT to `/_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}` — Bearer token auth in header
- Dual-format messages: plain-text `body` + HTML `formatted_body` (org.matrix.custom.html)
- Emoji header with status, loop details, optional output (truncated 500 chars) in both formats
- `GEN_LOOP_MATRIX_HOMESERVER`, `GEN_LOOP_MATRIX_ACCESS_TOKEN`, `GEN_LOOP_MATRIX_ROOM_ID` env vars
- `matrix_homeserver`, `matrix_access_token`, `matrix_room_id` parameters on `loop_schedule` tool
- `matrixHomeserver`, `matrixAccessToken`, `matrixRoomId` fields in loop entry notification object
- Own retry logic (3 attempts, 0/1/2s backoff) — uses PUT with Bearer auth, cannot reuse `_notify_webhook()`
- Unique `uuid4` transaction ID per notification attempt for Matrix idempotency
- "all" method now sends to file + webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + matrix + email (when configured)
- Fallback to file on Matrix failure (marked `_matrix_fallback: true`)
- 6 new tests (124 total): Matrix message structure, PUT method verification, retry/fallback, all-method integration

## [0.11.0] — Gotify Push Notifications (2026-02-02)

### Added
- **Gotify push notifications** — "gotify" as a first-class notification method
- JSON POST to `{server_url}/message?token={app_token}` — auth via URL query parameter
- Priority mapping by status: failed=8 (high), expired=5 (normal), completed=2 (low), cancelled=2 (low)
- Emoji title with status, plain-text body with loop details, optional output (truncated 500 chars)
- `GEN_LOOP_GOTIFY_SERVER_URL` and `GEN_LOOP_GOTIFY_APP_TOKEN` env vars
- `gotify_server_url` and `gotify_app_token` parameters on `loop_schedule` tool
- `gotifyServerUrl` and `gotifyAppToken` fields in loop entry notification object
- Reuses `_notify_webhook()` retry logic (same as Slack, Discord, Teams, ntfy, Pushover)
- Self-hosted only — supports any Gotify server instance
- "all" method now sends to file + webhook + slack + telegram + discord + teams + ntfy + pushover + gotify + email (when configured)
- Fallback to file on Gotify failure (marked `_gotify_fallback: true`)
- 6 new tests (118 total): Gotify message structure, priority mapping, retry/fallback, all-method integration

## [0.10.0] — Pushover Push Notifications (2026-02-02)

### Added
- **Pushover push notifications** — "pushover" as a first-class notification method
- JSON POST to `https://api.pushover.net/1/messages.json` with app token + user key
- Priority mapping by status: failed=1 (high), expired=0 (normal), completed=-1 (low), cancelled=-1 (low)
- Emoji title with status, plain-text body with loop details, optional output (truncated 500 chars)
- `GEN_LOOP_PUSHOVER_USER_KEY` and `GEN_LOOP_PUSHOVER_APP_TOKEN` env vars
- `pushover_user_key` and `pushover_app_token` parameters on `loop_schedule` tool
- `pushoverUserKey` and `pushoverAppToken` fields in loop entry notification object
- Reuses `_notify_webhook()` retry logic (same as Slack, Discord, Teams, ntfy)
- "all" method now sends to file + webhook + slack + telegram + discord + teams + ntfy + pushover + email (when configured)
- Fallback to file on Pushover failure (marked `_pushover_fallback: true`)
- 6 new tests (112 total): Pushover message structure, priority mapping, retry/fallback, all-method integration

## [0.9.0] — Email (SMTP) Notifications (2026-02-02)

### Added
- **Email notifications via SMTP** — "email" as a first-class notification method
- Plain-text email with emoji subject line (`{emoji} Loop {STATUS}: {loop_id}`), body with loop details, optional output
- STARTTLS (port 587) by default with configurable non-TLS fallback
- Multiple recipients via comma-separated `smtp_to` field
- Own retry logic (3 attempts, 0/1/2s backoff) — SMTP is not HTTP, does not reuse `_notify_webhook()`
- `GEN_LOOP_SMTP_SERVER`, `GEN_LOOP_SMTP_PORT` (default 587), `GEN_LOOP_SMTP_USERNAME`, `GEN_LOOP_SMTP_PASSWORD`, `GEN_LOOP_SMTP_FROM`, `GEN_LOOP_SMTP_TO`, `GEN_LOOP_SMTP_USE_TLS` (default true) env vars
- 7 SMTP parameters on `loop_schedule` tool + 7 fields in notification object
- "all" method now sends to file + webhook + slack + telegram + discord + teams + ntfy + email (when configured)
- Fallback to file on email failure (marked `_email_fallback: true`)
- 6 new tests (106 total): SMTP connection, message structure, retry/fallback, multiple recipients, all-method integration

## [0.8.0] — Ntfy.sh Push Notifications (2026-02-01)

### Added
- **Ntfy.sh push notifications** — "ntfy" as a first-class notification method
- JSON message formatting: emoji title, plain-text body with loop details, priority mapping (failed=5/urgent, expired=4/high, completed=3/default, cancelled=2/low), emoji tags (ntfy shortcodes)
- Supports self-hosted ntfy instances via configurable server URL
- `GEN_LOOP_NTFY_SERVER` env var for ntfy server URL (default: `https://ntfy.sh`)
- `GEN_LOOP_NTFY_TOPIC` env var for ntfy topic name
- `ntfy_server` and `ntfy_topic` parameters on `loop_schedule` tool
- `ntfyServer` and `ntfyTopic` fields in loop entry notification object
- "all" method now sends to file + webhook + slack + telegram + discord + teams + ntfy (when configured)
- Fallback to file on ntfy failure (marked `_ntfy_fallback: true`)
- 6 new tests (100 total): ntfy message structure, priority/tags, retry/fallback, all-method integration

## [0.7.0] — Microsoft Teams Webhook Notifications (2026-02-01)

### Added
- **Microsoft Teams webhook notifications** — "teams" as a first-class notification method
- Adaptive Card formatting: colored Container (good/attention/warning/accent/default by status), FactSet with loop details, optional monospace output block, subtle footer
- Uses Power Automate Workflows webhooks (Microsoft's replacement for retired O365 connectors)
- `GEN_LOOP_TEAMS_WEBHOOK_URL` env var for default Teams webhook URL
- `teams_webhook_url` parameter on `loop_schedule` tool
- `teamsWebhookUrl` field in loop entry notification object
- "all" method now sends to file + webhook + slack + telegram + discord + teams (when configured)
- Fallback to file on Teams failure (marked `_teams_fallback: true`)
- 6 new tests (94 total): Teams Adaptive Card structure, retry/fallback, all-method integration

## [0.6.0] — Discord Webhook Notifications (2026-02-01)

### Added
- **Discord webhook notifications** — "discord" as a first-class notification method
- Rich embed formatting: colored sidebar (green/red/orange/blue/grey by status), emoji title, inline fields, optional output in code block, footer
- `GEN_LOOP_DISCORD_WEBHOOK_URL` env var for default Discord webhook URL
- `discord_webhook_url` parameter on `loop_schedule` tool
- `discordWebhookUrl` field in loop entry notification object
- "all" method now sends to file + webhook + slack + telegram + discord (when configured)
- Fallback to file on Discord failure (marked `_discord_fallback: true`)
- 6 new tests (88 total): Discord embed structure, retry/fallback, all-method integration

## [0.5.0] — Telegram Bot Notifications (2026-01-31)

### Added
- **Telegram Bot notifications** — "telegram" as a first-class notification method
- HTML formatting: bold header with status emoji, code-wrapped loop ID, optional pre-formatted output, italic footer
- `html.escape()` on user-provided values to prevent Telegram HTML parse errors
- `GEN_LOOP_TELEGRAM_BOT_TOKEN` and `GEN_LOOP_TELEGRAM_CHAT_ID` env vars for default config
- `telegram_bot_token` and `telegram_chat_id` parameters on `loop_schedule` tool
- `telegramBotToken` and `telegramChatId` fields in loop entry notification object
- "all" method now sends to file + webhook + slack + telegram (when configured)
- Fallback to file on Telegram failure (marked `_telegram_fallback: true`)
- 6 new tests (82 total): Telegram message structure, retry/fallback, all-method integration

## [0.4.0] — Slack Notifications (2026-01-31)

### Added
- **Slack webhook notifications** — "slack" as a first-class notification method
- Slack Block Kit formatting: header with status emoji, fields (loop ID, status, task, attempts), optional output block, context footer
- `GEN_LOOP_SLACK_WEBHOOK_URL` env var for default Slack webhook URL
- `slack_webhook_url` parameter on `loop_schedule` tool
- `slackWebhookUrl` field in loop entry notification object
- "all" method now sends to file + webhook + slack (when URLs configured)
- Fallback to file on Slack failure (marked `_slack_fallback: true`)
- 6 new tests (76 total): Slack payload structure, retry/fallback, all-method integration

## [0.3.0] — CLI Tool + Templates (2026-01-31)

### Added
- **CLI tool** (`gen-loop-cli`) for store inspection and management — 7 subcommands: list, show, dashboard, history, cancel, batch, stats
- `--json` output mode for list, show, and stats subcommands
- `--store-dir` global option to override `GEN_LOOP_STORE_DIR`
- 2 new templates: `systemd_service` (systemctl check), `dns_resolve` (dig check)
- 18 new tests (70 total): 15 CLI tests, 3 template tests

### Changed
- Template count: 8 → 10

## [0.2.0] — Improvements (2026-01-31)

### Fixed
- Batch `cleanup_done` no longer abuses `and` for side effects in list comprehension — uses explicit for-loop
- Default `STORE_DIR` changed from legacy `~/projects/nelly-projects/...` to `~/.gen-loop/loop-store`
- HTTP check and webhook User-Agent now use dynamic version from `__version__`

### Added
- Webhook retry with fallback — 2 retries with 1s/2s backoff; falls back to file notification (marked `_webhook_fallback: true`) on exhaustion
- Notification file rotation — `notifications.jsonl` rotates to `.jsonl.1` when exceeding 1MB
- Concurrency limit — `GEN_LOOP_MAX_CONCURRENT` env var (default 5) limits concurrent check threads via semaphore
- 4 new templates: `docker_health`, `database_ready`, `process_running`, `port_listening`
- HTTP read limit increased from 4096 to 16384 bytes, extracted as `HTTP_READ_LIMIT` constant
- 10 new tests (52 total): webhook retry/fallback, file rotation, concurrency limit, HTTP read limit, new templates

### Changed
- `loop_schedule_template` docstring now lists all 8 available templates

## [0.1.0] — All Phases (2026-01-31)

### Added
- Thread-safe file store (fcntl + threading.Lock for cross-thread + cross-process safety)
- Atomic writes (write-to-temp, rename) for crash resilience
- Internal scheduler thread (daemon, configurable poll interval)
- Recovery on startup (fire overdue, expire old)
- 4 check types: shell, file_exists, http, grep
- Notification system: file (JSONL), webhook (POST), stderr
- 9 MCP tools: schedule, check, list, cancel, history, templates, dashboard, batch, write_result
- 4 templates: install_check, build_check, deploy_check, download_check
- Graceful shutdown (SIGTERM/SIGINT handlers)
- Env var configuration (store dir, poll interval, notify method)
- 42 tests (store, checks, scheduler, notifier, integration)
- Full project docs: PLAN, ARCHITECTURE, folder READMEs, scenarios

---

## See Also

- [Getting Started](../01-user-guide/01-getting-started.md)
- [Installation](../01-user-guide/02-installation.md)
- [Quick Start](../01-user-guide/03-quick-start.md)
- [Worked Examples](../01-user-guide/04-worked-examples.md)
- [Overview](../02-api-reference/01-overview.md)

---

Previous: [FAQ](02-faq.md)