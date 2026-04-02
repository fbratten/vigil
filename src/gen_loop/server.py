"""Gen-Loop MCP Server — standalone self-scheduling follow-up system."""

import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from gen_loop.store import LoopStore
from gen_loop.checks import run_check
from gen_loop.notifier import Notifier
from gen_loop.scheduler import SchedulerThread

# Configuration via env vars
STORE_DIR = os.environ.get(
    "GEN_LOOP_STORE_DIR",
    str(Path.home() / ".gen-loop" / "loop-store"),
)
POLL_INTERVAL = float(os.environ.get("GEN_LOOP_POLL_INTERVAL", "10"))
DEFAULT_NOTIFY = os.environ.get("GEN_LOOP_NOTIFY", "file")
MAX_CONCURRENT = int(os.environ.get("GEN_LOOP_MAX_CONCURRENT", "5"))
DEFAULT_SLACK_WEBHOOK_URL = os.environ.get("GEN_LOOP_SLACK_WEBHOOK_URL", "")
DEFAULT_TELEGRAM_BOT_TOKEN = os.environ.get("GEN_LOOP_TELEGRAM_BOT_TOKEN", "")
DEFAULT_TELEGRAM_CHAT_ID = os.environ.get("GEN_LOOP_TELEGRAM_CHAT_ID", "")
DEFAULT_DISCORD_WEBHOOK_URL = os.environ.get("GEN_LOOP_DISCORD_WEBHOOK_URL", "")
DEFAULT_TEAMS_WEBHOOK_URL = os.environ.get("GEN_LOOP_TEAMS_WEBHOOK_URL", "")
DEFAULT_NTFY_SERVER = os.environ.get("GEN_LOOP_NTFY_SERVER", "https://ntfy.sh")
DEFAULT_NTFY_TOPIC = os.environ.get("GEN_LOOP_NTFY_TOPIC", "")
DEFAULT_PUSHOVER_USER_KEY = os.environ.get("GEN_LOOP_PUSHOVER_USER_KEY", "")
DEFAULT_PUSHOVER_APP_TOKEN = os.environ.get("GEN_LOOP_PUSHOVER_APP_TOKEN", "")
DEFAULT_GOTIFY_SERVER_URL = os.environ.get("GEN_LOOP_GOTIFY_SERVER_URL", "")
DEFAULT_GOTIFY_APP_TOKEN = os.environ.get("GEN_LOOP_GOTIFY_APP_TOKEN", "")
DEFAULT_MATRIX_HOMESERVER = os.environ.get("GEN_LOOP_MATRIX_HOMESERVER", "")
DEFAULT_MATRIX_ACCESS_TOKEN = os.environ.get("GEN_LOOP_MATRIX_ACCESS_TOKEN", "")
DEFAULT_MATRIX_ROOM_ID = os.environ.get("GEN_LOOP_MATRIX_ROOM_ID", "")
DEFAULT_TWILIO_ACCOUNT_SID = os.environ.get("GEN_LOOP_TWILIO_ACCOUNT_SID", "")
DEFAULT_TWILIO_AUTH_TOKEN = os.environ.get("GEN_LOOP_TWILIO_AUTH_TOKEN", "")
DEFAULT_TWILIO_FROM_NUMBER = os.environ.get("GEN_LOOP_TWILIO_FROM_NUMBER", "")
DEFAULT_TWILIO_TO_NUMBER = os.environ.get("GEN_LOOP_TWILIO_TO_NUMBER", "")
DEFAULT_GOOGLE_CHAT_WEBHOOK_URL = os.environ.get("GEN_LOOP_GOOGLE_CHAT_WEBHOOK_URL", "")
DEFAULT_SMTP_SERVER = os.environ.get("GEN_LOOP_SMTP_SERVER", "")
DEFAULT_SMTP_PORT = int(os.environ.get("GEN_LOOP_SMTP_PORT", "587"))
DEFAULT_SMTP_USERNAME = os.environ.get("GEN_LOOP_SMTP_USERNAME", "")
DEFAULT_SMTP_PASSWORD = os.environ.get("GEN_LOOP_SMTP_PASSWORD", "")
DEFAULT_SMTP_FROM = os.environ.get("GEN_LOOP_SMTP_FROM", "")
DEFAULT_SMTP_TO = os.environ.get("GEN_LOOP_SMTP_TO", "")
DEFAULT_SMTP_USE_TLS = os.environ.get("GEN_LOOP_SMTP_USE_TLS", "true").lower() == "true"

mcp = FastMCP(
    "gen-loop",
    instructions="""gen-loop: Self-scheduling follow-up system with check-based monitoring and notifications.

Schedules tasks that need to be checked later — like build status, deployment health,
or async operations. Each task has a check command (shell, HTTP, file, process), retry
logic with backoff, expiry, and multi-channel notifications (Slack, Telegram, Discord,
email, ntfy, Pushover, Gotify, Matrix, Twilio, Google Chat, Teams).

TOOL SELECTION GUIDE:
- Schedule a follow-up    → loop_schedule (task, check_command, check_after_minutes)
- List active tasks        → loop_list (filter by status)
- Check one task now       → loop_check (task_id) — run check immediately
- Cancel a task            → loop_cancel (task_id)
- Get task details         → loop_get (task_id)
- View event history       → loop_events (task_id or all)
- Start scheduler          → loop_start — begin background polling
- Stop scheduler           → loop_stop — halt background polling
- Configure notifications  → loop_configure_notify (method, webhook_url, etc.)

TYPICAL WORKFLOW: loop_schedule → loop_start → (scheduler runs checks automatically)
→ loop_list to monitor → loop_events for history.

CHECK TYPES: shell (run command, exit 0 = success), http (GET URL, 2xx = success),
file (check file exists/modified), process (check PID running).

IMPORTANT: The scheduler runs as a background thread. Call loop_start to activate it.
Tasks expire after expires_after_hours (default 24). Retries use configurable backoff.""",
)
store = LoopStore(STORE_DIR)
notifier = Notifier(STORE_DIR, default_method=DEFAULT_NOTIFY)
scheduler = SchedulerThread(
    store=store,
    poll_interval=POLL_INTERVAL,
    on_event=notifier.notify,
    max_concurrent=MAX_CONCURRENT,
)


# --- Phase 1: Core Tools ---

@mcp.tool()
def loop_schedule(
    task: str,
    check_command: str = "",
    check_type: str = "shell",
    success_criteria: str = "",
    context_why: str = "",
    context_started_by: str = "",
    related_files: str = "",
    check_after_minutes: int = 5,
    max_retries: int = 3,
    retry_backoff_minutes: str = "5,15,60",
    expires_after_hours: int = 24,
    notify_method: str = "",
    webhook_url: str = "",
    slack_webhook_url: str = "",
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    discord_webhook_url: str = "",
    teams_webhook_url: str = "",
    ntfy_server: str = "",
    ntfy_topic: str = "",
    pushover_user_key: str = "",
    pushover_app_token: str = "",
    gotify_server_url: str = "",
    gotify_app_token: str = "",
    matrix_homeserver: str = "",
    matrix_access_token: str = "",
    matrix_room_id: str = "",
    twilio_account_sid: str = "",
    twilio_auth_token: str = "",
    twilio_from_number: str = "",
    twilio_to_number: str = "",
    google_chat_webhook_url: str = "",
    smtp_server: str = "",
    smtp_port: int = 587,
    smtp_username: str = "",
    smtp_password: str = "",
    smtp_from: str = "",
    smtp_to: str = "",
    smtp_use_tls: bool = True,
) -> str:
    """Schedule a self-managed follow-up check. No external scheduler needed.

    The internal scheduler thread will fire the check automatically.

    Args:
        task: What to check (human-readable).
        check_command: Command/path/URL to run.
        check_type: shell, file_exists, http, or grep.
        success_criteria: Substring match for success.
        context_why: Why this loop exists.
        context_started_by: What triggered it.
        related_files: Comma-separated paths.
        check_after_minutes: Delay before first check (default 5).
        max_retries: Max attempts (default 3).
        retry_backoff_minutes: Backoff schedule (default "5,15,60").
        expires_after_hours: Expiry (default 24).
        notify_method: file, webhook, slack, telegram, discord, teams, ntfy, pushover, gotify, matrix, twilio_sms, google_chat, email, none, or all (default from env).
        webhook_url: URL for webhook notifications.
        slack_webhook_url: Slack Incoming Webhook URL for Slack notifications.
        telegram_bot_token: Telegram Bot API token for Telegram notifications.
        telegram_chat_id: Telegram chat/group ID for Telegram notifications.
        discord_webhook_url: Discord Incoming Webhook URL for Discord notifications.
        teams_webhook_url: Microsoft Teams Workflow Webhook URL for Teams notifications.
        ntfy_server: Ntfy server URL (default https://ntfy.sh, supports self-hosted).
        ntfy_topic: Ntfy topic name for push notifications.
        pushover_user_key: Pushover user key for push notifications.
        pushover_app_token: Pushover application API token.
        gotify_server_url: Gotify server URL (e.g., https://gotify.example.com).
        gotify_app_token: Gotify application token for push notifications.
        matrix_homeserver: Matrix homeserver URL (e.g., https://matrix.org).
        matrix_access_token: Matrix access token for authentication.
        matrix_room_id: Matrix room ID (e.g., !roomid:matrix.org).
        twilio_account_sid: Twilio Account SID for SMS notifications.
        twilio_auth_token: Twilio Auth Token for SMS notifications.
        twilio_from_number: Twilio phone number to send from (E.164 format, e.g., +12125551234).
        twilio_to_number: Recipient phone number (E.164 format, e.g., +13105555555).
        google_chat_webhook_url: Google Chat Incoming Webhook URL for Google Chat notifications.
        smtp_server: SMTP server hostname (e.g., smtp.gmail.com).
        smtp_port: SMTP port (default 587 for STARTTLS).
        smtp_username: SMTP authentication username.
        smtp_password: SMTP authentication password.
        smtp_from: Sender email address.
        smtp_to: Recipient email address(es), comma-separated.
        smtp_use_tls: Use STARTTLS encryption (default true).
    """
    context = {}
    if context_why:
        context["why"] = context_why
    if context_started_by:
        context["startedBy"] = context_started_by
    if related_files:
        context["relatedFiles"] = [f.strip() for f in related_files.split(",")]

    backoff = [int(m.strip()) for m in retry_backoff_minutes.split(",")]

    entry = store.create(
        task=task,
        check_type=check_type,
        check_command=check_command,
        success_criteria=success_criteria,
        context=context,
        check_after_minutes=check_after_minutes,
        max_retries=max_retries,
        retry_backoff_minutes=backoff,
        expires_after_hours=expires_after_hours,
        notify_method=notify_method or DEFAULT_NOTIFY,
        webhook_url=webhook_url,
        slack_webhook_url=slack_webhook_url or DEFAULT_SLACK_WEBHOOK_URL,
        telegram_bot_token=telegram_bot_token or DEFAULT_TELEGRAM_BOT_TOKEN,
        telegram_chat_id=telegram_chat_id or DEFAULT_TELEGRAM_CHAT_ID,
        discord_webhook_url=discord_webhook_url or DEFAULT_DISCORD_WEBHOOK_URL,
        teams_webhook_url=teams_webhook_url or DEFAULT_TEAMS_WEBHOOK_URL,
        ntfy_server=ntfy_server or DEFAULT_NTFY_SERVER,
        ntfy_topic=ntfy_topic or DEFAULT_NTFY_TOPIC,
        pushover_user_key=pushover_user_key or DEFAULT_PUSHOVER_USER_KEY,
        pushover_app_token=pushover_app_token or DEFAULT_PUSHOVER_APP_TOKEN,
        gotify_server_url=gotify_server_url or DEFAULT_GOTIFY_SERVER_URL,
        gotify_app_token=gotify_app_token or DEFAULT_GOTIFY_APP_TOKEN,
        matrix_homeserver=matrix_homeserver or DEFAULT_MATRIX_HOMESERVER,
        matrix_access_token=matrix_access_token or DEFAULT_MATRIX_ACCESS_TOKEN,
        matrix_room_id=matrix_room_id or DEFAULT_MATRIX_ROOM_ID,
        twilio_account_sid=twilio_account_sid or DEFAULT_TWILIO_ACCOUNT_SID,
        twilio_auth_token=twilio_auth_token or DEFAULT_TWILIO_AUTH_TOKEN,
        twilio_from_number=twilio_from_number or DEFAULT_TWILIO_FROM_NUMBER,
        twilio_to_number=twilio_to_number or DEFAULT_TWILIO_TO_NUMBER,
        google_chat_webhook_url=google_chat_webhook_url or DEFAULT_GOOGLE_CHAT_WEBHOOK_URL,
        smtp_server=smtp_server or DEFAULT_SMTP_SERVER,
        smtp_port=smtp_port or DEFAULT_SMTP_PORT,
        smtp_username=smtp_username or DEFAULT_SMTP_USERNAME,
        smtp_password=smtp_password or DEFAULT_SMTP_PASSWORD,
        smtp_from=smtp_from or DEFAULT_SMTP_FROM,
        smtp_to=smtp_to or DEFAULT_SMTP_TO,
        smtp_use_tls=smtp_use_tls if smtp_server else DEFAULT_SMTP_USE_TLS,
    )

    return json.dumps({
        "status": "scheduled",
        "loop_id": entry["id"],
        "task": task,
        "first_check_in": f"{check_after_minutes}m",
        "max_retries": max_retries,
        "scheduler": "internal (self-managed)",
    }, indent=2)


@mcp.tool()
def loop_check(loop_id: str) -> str:
    """Manually trigger a check for a loop (bypasses scheduler timing).

    Args:
        loop_id: Loop to check (e.g., "loop-001").
    """
    entry = store.get(loop_id)
    if entry is None:
        return json.dumps({"error": f"Loop {loop_id} not found"})
    if entry["status"] != "active":
        return json.dumps({"error": f"Loop {loop_id} is {entry['status']}, not active"})

    # Check expiry
    expires_at = entry["schedule"].get("expiresAt")
    if expires_at:
        now = datetime.now(timezone.utc)
        try:
            if now > datetime.fromisoformat(expires_at):
                store.set_status(loop_id, "expired")
                store.add_history(loop_id, result="expired", note="Loop expired")
                return json.dumps({"loop_id": loop_id, "result": "expired", "task": entry["task"]})
        except (ValueError, TypeError):
            pass

    check = entry["check"]
    result = run_check(check["type"], check["command"], check.get("successCriteria", ""))

    if result.success:
        store.add_history(loop_id, result="success", output=result.output, note="Manual check passed")
        store.set_status(loop_id, "completed")
        notifier.notify(entry, "completed", result)
        return json.dumps({
            "loop_id": loop_id, "result": "success", "task": entry["task"],
            "output": result.output[:500], "status": "completed",
        }, indent=2)

    attempt = entry["state"]["attempt"] + 1
    max_retries = entry["schedule"]["maxRetries"]
    store.add_history(loop_id, result="failure", output=result.output or result.error,
                      note=f"Manual check {attempt}/{max_retries}")

    if attempt >= max_retries:
        store.set_status(loop_id, "failed")
        notifier.notify(entry, "failed", result)
        return json.dumps({
            "loop_id": loop_id, "result": "failed", "task": entry["task"],
            "output": result.output or result.error, "status": "failed",
        }, indent=2)

    from datetime import timedelta
    backoff_list = entry["schedule"].get("retryBackoffMs", [300000])
    backoff_idx = min(attempt - 1, len(backoff_list) - 1)
    next_delay_ms = backoff_list[backoff_idx]
    next_check_at = (datetime.now(timezone.utc) + timedelta(milliseconds=next_delay_ms)).isoformat()
    store.set_next_check(loop_id, next_check_at)

    return json.dumps({
        "loop_id": loop_id, "result": "retry", "task": entry["task"],
        "output": result.output or result.error,
        "attempt": attempt, "max_retries": max_retries,
        "next_check_in": f"{next_delay_ms // 60000}m", "status": "active",
    }, indent=2)


@mcp.tool()
def loop_list(status: str = "") -> str:
    """List all loops, optionally filtered by status."""
    entries = store.list_all(status=status or None)
    summaries = [{
        "id": e["id"], "status": e["status"], "task": e["task"],
        "attempts": e["state"]["attempt"], "max_retries": e["schedule"]["maxRetries"],
        "created": e["created"], "next_check": e["state"].get("nextCheckAt"),
    } for e in entries]
    return json.dumps(summaries, indent=2)


@mcp.tool()
def loop_cancel(loop_id: str) -> str:
    """Cancel an active loop."""
    entry = store.get(loop_id)
    if entry is None:
        return json.dumps({"error": f"Loop {loop_id} not found"})
    store.set_status(loop_id, "cancelled")
    store.add_history(loop_id, result="cancelled", note="Manually cancelled")
    notifier.notify(entry, "cancelled")
    return json.dumps({"loop_id": loop_id, "status": "cancelled", "task": entry["task"]}, indent=2)


# --- Phase 3: Intelligence ---

@mcp.tool()
def loop_history(status: str = "", keyword: str = "", limit: int = 20) -> str:
    """View past loops with stats."""
    if status:
        entries = store.list_all(status=status)
    else:
        entries = [e for e in store.list_all() if e["status"] != "active"]

    if keyword:
        entries = [e for e in entries if keyword.lower() in e["task"].lower()]

    entries.sort(key=lambda e: e.get("updated", ""), reverse=True)
    entries = entries[:limit]

    all_done = [e for e in store.list_all() if e["status"] != "active"]
    total = len(all_done)
    by_status = {}
    total_attempts = 0
    for e in all_done:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        total_attempts += e["state"]["attempt"]

    return json.dumps({
        "entries": [{"id": e["id"], "status": e["status"], "task": e["task"],
                     "attempts": e["state"]["attempt"], "updated": e.get("updated", "")} for e in entries],
        "stats": {
            "total": total, "by_status": by_status,
            "avg_attempts": round(total_attempts / total, 1) if total else 0,
            "success_rate_pct": round(by_status.get("completed", 0) / total * 100, 1) if total else 0,
        },
    }, indent=2)


@mcp.tool()
def loop_schedule_template(
    template: str, target: str = "", check_after_minutes: int = 5,
    max_retries: int = 3, context_why: str = "",
) -> str:
    """Schedule using a pre-defined template.

    Available: install_check, build_check, deploy_check, download_check,
    docker_health, database_ready, process_running, port_listening,
    systemd_service, dns_resolve.
    """
    from gen_loop.templates import TEMPLATES, apply_template
    if template not in TEMPLATES:
        return json.dumps({"error": f"Unknown template: {template}", "available": list(TEMPLATES.keys())})
    params = apply_template(template, target)
    params["check_after_minutes"] = check_after_minutes
    params["max_retries"] = max_retries
    if context_why:
        params["context_why"] = context_why
    return loop_schedule(**params)


@mcp.tool()
def loop_dashboard() -> str:
    """Formatted overview of all loops — active + recent."""
    active = store.list_all(status="active")
    recent_done = sorted(
        [e for e in store.list_all() if e["status"] != "active"],
        key=lambda e: e.get("updated", ""), reverse=True,
    )[:5]

    lines = ["## 🔄 Gen-Loop Dashboard\n"]
    if not active and not recent_done:
        lines.append("No loops. All quiet.")
        return "\n".join(lines)

    if active:
        lines.append(f"### Active ({len(active)})")
        for e in active:
            lines.append(f"- **{e['id']}** — {e['task']} "
                         f"(attempt {e['state']['attempt']}/{e['schedule']['maxRetries']}, "
                         f"next: {e['state'].get('nextCheckAt', 'unknown')})")
        lines.append("")

    if recent_done:
        lines.append("### Recent")
        emoji_map = {"completed": "✅", "failed": "❌", "expired": "⏰", "cancelled": "🚫"}
        for e in recent_done:
            lines.append(f"- {emoji_map.get(e['status'], '📝')} **{e['id']}** — {e['task']} "
                         f"({e['status']}, {e['state']['attempt']} attempts)")

    all_entries = store.list_all()
    by_status = {}
    for e in all_entries:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    lines.append(f"\n**Total:** {len(all_entries)} — " + ", ".join(f"{v} {k}" for k, v in by_status.items()))
    lines.append(f"**Scheduler:** running (poll every {POLL_INTERVAL}s)")

    return "\n".join(lines)


@mcp.tool()
def loop_batch(action: str) -> str:
    """Batch operations: cancel_expired, retry_failed, cleanup_done, summary."""
    if action == "cancel_expired":
        expired = store.list_all(status="expired")
        for e in expired:
            store.set_status(e["id"], "cancelled")
            store.add_history(e["id"], result="cancelled", note="Batch cleanup")
        return json.dumps({"action": action, "affected": len(expired)})

    elif action == "retry_failed":
        failed = store.list_all(status="failed")
        for e in failed:
            store.set_status(e["id"], "active")
            store.add_history(e["id"], result="retry", note="Batch retry")
        return json.dumps({"action": action, "affected": len(failed)})

    elif action == "cleanup_done":
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        completed = store.list_all(status="completed")
        archived = 0
        for e in completed:
            if e.get("updated", "") < cutoff:
                store.set_status(e["id"], "archived")
                archived += 1
        return json.dumps({"action": action, "archived": archived})

    elif action == "summary":
        by_status = {}
        for e in store.list_all():
            by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        return json.dumps({"action": action, "total": sum(by_status.values()), "by_status": by_status})

    return json.dumps({"error": f"Unknown: {action}", "available": ["cancel_expired", "retry_failed", "cleanup_done", "summary"]})


@mcp.tool()
def loop_write_result(loop_id: str, file_path: str = "") -> str:
    """Write a loop's result to a file (markdown format).

    Args:
        loop_id: Loop to write (must be non-active).
        file_path: Target file path. Defaults to loop-store/results.md.
    """
    entry = store.get(loop_id)
    if entry is None:
        return json.dumps({"error": f"Loop {loop_id} not found"})
    if entry["status"] == "active":
        return json.dumps({"error": "Loop still active"})

    if not file_path:
        file_path = str(Path(STORE_DIR) / "results.md")

    emoji = {"completed": "✅", "failed": "❌", "expired": "⏰", "cancelled": "🚫"}.get(entry["status"], "📝")
    last_output = ""
    if entry["state"]["history"]:
        last_output = entry["state"]["history"][-1].get("output", "")[:200]

    text = (f"\n### Loop {entry['id']} {emoji} {entry['status']}\n"
            f"- **Task:** {entry['task']}\n"
            f"- **Attempts:** {entry['state']['attempt']}\n")
    if last_output:
        text += f"- **Output:** `{last_output}`\n"
    if entry.get("context", {}).get("why"):
        text += f"- **Context:** {entry['context']['why']}\n"

    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "a") as f:
        f.write(text)

    return json.dumps({"loop_id": loop_id, "written_to": file_path, "status": entry["status"]}, indent=2)


def main():
    """Run the Gen-Loop MCP server with internal scheduler."""
    # Graceful shutdown
    def _shutdown(sig, frame):
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Start scheduler
    scheduler.start()

    # Run MCP server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
