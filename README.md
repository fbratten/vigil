# Gen-Loop MCP Server 🔄

**Standalone** self-scheduling follow-up system for AI agents. No external scheduler, no gateway, no cron — manages everything internally.

## Why?

`loop-mcp` needs OpenClaw. This doesn't. Plug it into **any** MCP client (desktop apps, IDE extensions, custom agents) and it just works.

## How It Works

1. Agent calls `loop_schedule` with a task + check command
2. Internal scheduler thread polls every 10s
3. When it's time, the check runs automatically
4. Success → loop closes. Failure → retry with backoff. Timeout → expire.
5. Notifications via file (JSONL), webhook (POST), Slack (Block Kit), Telegram (Bot API), Discord (Embeds), Teams (Adaptive Cards), ntfy.sh (push), Pushover (push), Gotify (push), Matrix (Client-Server API), Twilio SMS, Google Chat (Cards v2), email (SMTP), or stderr

## MCP Tools (9)

| Tool | Description |
|------|-------------|
| `loop_schedule` | Schedule a follow-up check |
| `loop_check` | Manually trigger a check |
| `loop_list` | List loops by status |
| `loop_cancel` | Cancel an active loop |
| `loop_history` | View past loops with stats |
| `loop_schedule_template` | Use templates (10 types — see below) |
| `loop_dashboard` | Formatted overview |
| `loop_batch` | Batch ops (cancel expired, retry failed, etc.) |
| `loop_write_result` | Write result to any file |

## Check Types

- `shell` — command exit code or output match
- `file_exists` — file appeared at path
- `http` — GET URL, check status/body (reads up to 16KB)
- `grep` — search file for pattern (`pattern::filepath`)

## Templates (10)

| Template | Check Type | Use Case |
|----------|-----------|----------|
| `install_check` | shell | Verify package installed |
| `build_check` | file_exists | Verify build artifact |
| `deploy_check` | http | Verify deployment live |
| `download_check` | file_exists | Verify file downloaded |
| `docker_health` | shell | Verify container healthy |
| `database_ready` | shell | Verify DB accepting connections |
| `process_running` | shell | Verify process is running |
| `port_listening` | shell | Verify port is listening |
| `systemd_service` | shell | Verify systemd service active |
| `dns_resolve` | shell | Verify DNS resolution |

## Configuration (env vars)

| Var | Default | Description |
|-----|---------|-------------|
| `GEN_LOOP_STORE_DIR` | `~/.gen-loop/loop-store` | Store location |
| `GEN_LOOP_POLL_INTERVAL` | `10` | Scheduler poll interval (seconds) |
| `GEN_LOOP_NOTIFY` | `file` | Default notification method (file, webhook, slack, telegram, discord, teams, ntfy, pushover, gotify, matrix, twilio_sms, google_chat, email, all) |
| `GEN_LOOP_WEBHOOK_URL` | _(empty)_ | Default webhook URL |
| `GEN_LOOP_SLACK_WEBHOOK_URL` | _(empty)_ | Default Slack Incoming Webhook URL |
| `GEN_LOOP_TELEGRAM_BOT_TOKEN` | _(empty)_ | Default Telegram Bot API token |
| `GEN_LOOP_TELEGRAM_CHAT_ID` | _(empty)_ | Default Telegram chat/group ID |
| `GEN_LOOP_DISCORD_WEBHOOK_URL` | _(empty)_ | Default Discord Incoming Webhook URL |
| `GEN_LOOP_TEAMS_WEBHOOK_URL` | _(empty)_ | Default Microsoft Teams Workflow Webhook URL |
| `GEN_LOOP_NTFY_SERVER` | `https://ntfy.sh` | Ntfy server URL (supports self-hosted) |
| `GEN_LOOP_NTFY_TOPIC` | _(empty)_ | Ntfy topic name for push notifications |
| `GEN_LOOP_PUSHOVER_USER_KEY` | _(empty)_ | Pushover user key |
| `GEN_LOOP_PUSHOVER_APP_TOKEN` | _(empty)_ | Pushover application API token |
| `GEN_LOOP_GOTIFY_SERVER_URL` | _(empty)_ | Gotify server URL (e.g., https://gotify.example.com) |
| `GEN_LOOP_GOTIFY_APP_TOKEN` | _(empty)_ | Gotify application token |
| `GEN_LOOP_MATRIX_HOMESERVER` | _(empty)_ | Matrix homeserver URL (e.g., https://matrix.example.com) |
| `GEN_LOOP_MATRIX_ACCESS_TOKEN` | _(empty)_ | Matrix access token (Bearer auth) |
| `GEN_LOOP_MATRIX_ROOM_ID` | _(empty)_ | Matrix room ID (e.g., !abc:matrix.example.com) |
| `GEN_LOOP_TWILIO_ACCOUNT_SID` | _(empty)_ | Twilio Account SID |
| `GEN_LOOP_TWILIO_AUTH_TOKEN` | _(empty)_ | Twilio Auth Token |
| `GEN_LOOP_TWILIO_FROM_NUMBER` | _(empty)_ | Twilio phone number (E.164 format, e.g., +12125551234) |
| `GEN_LOOP_TWILIO_TO_NUMBER` | _(empty)_ | Recipient phone number (E.164 format) |
| `GEN_LOOP_GOOGLE_CHAT_WEBHOOK_URL` | _(empty)_ | Google Chat Incoming Webhook URL |
| `GEN_LOOP_SMTP_SERVER` | _(empty)_ | SMTP server hostname (e.g., smtp.gmail.com) |
| `GEN_LOOP_SMTP_PORT` | `587` | SMTP port (587 for STARTTLS) |
| `GEN_LOOP_SMTP_USERNAME` | _(empty)_ | SMTP authentication username |
| `GEN_LOOP_SMTP_PASSWORD` | _(empty)_ | SMTP authentication password |
| `GEN_LOOP_SMTP_FROM` | _(empty)_ | Sender email address |
| `GEN_LOOP_SMTP_TO` | _(empty)_ | Recipient email address(es), comma-separated |
| `GEN_LOOP_SMTP_USE_TLS` | `true` | Use STARTTLS encryption |
| `GEN_LOOP_MAX_CONCURRENT` | `5` | Max concurrent check threads |

## CLI Tool (`gen-loop-cli`)

Inspect and manage the loop store from the command line — no MCP client needed.

```bash
gen-loop-cli list                      # List all loops
gen-loop-cli list --status active      # Filter by status
gen-loop-cli list --json               # JSON output
gen-loop-cli show loop-001             # Show loop details
gen-loop-cli dashboard                 # Overview of active + recent
gen-loop-cli history --limit 10        # Recent history entries
gen-loop-cli stats --json              # Aggregate statistics
gen-loop-cli cancel loop-001 --yes     # Cancel a loop
gen-loop-cli batch summary             # Status summary
gen-loop-cli batch cancel_expired      # Batch cancel expired loops
gen-loop-cli notifications             # Query notification history
gen-loop-cli notifications --loop-id loop-001 --event completed --limit 20
gen-loop-cli notifications --include-rotated --json
```

## Quick Start

```bash
# Install
cd gen-loop-mcp && uv pip install -e ".[dev]"

# Run tests (148 tests)
pytest tests/ -v

# Use via mcporter
mcporter call gen-loop.loop_schedule task="Check build" check_command="ls dist/" check_after_minutes=2
mcporter call gen-loop.loop_dashboard
mcporter call gen-loop.loop_list

# Use CLI directly
gen-loop-cli list
gen-loop-cli dashboard
```

## Version

0.15.0 — Notification history CLI, Google Chat, Twilio SMS, Matrix, Gotify, Pushover, Email, Ntfy.sh, Teams, Discord, Telegram, Slack notifications, CLI tool (8 subcommands), 10 templates, 148 tests.
