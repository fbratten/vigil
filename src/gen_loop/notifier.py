"""Notification delivery — file, webhook, Slack, Telegram, Discord, Teams, ntfy, Pushover, Gotify, Matrix, Twilio SMS, Google Chat, email, stderr."""

import html
import json
import smtplib
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from gen_loop import __version__

ROTATION_SIZE_BYTES = 1_048_576  # 1 MB


class Notifier:
    """Routes notifications to file, webhook, or stderr."""

    def __init__(self, store_dir: str | Path, default_method: str = "file"):
        self.store_dir = Path(store_dir)
        self.notifications_file = self.store_dir / "notifications.jsonl"
        self.default_method = default_method

    def notify(self, entry: dict[str, Any], event_type: str, check_result: Any = None):
        """Send notification for a loop event."""
        method = entry.get("notification", {}).get("method") or self.default_method

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "loop_id": entry["id"],
            "event": event_type,
            "task": entry["task"],
            "status": entry.get("status", "unknown"),
            "attempts": entry["state"]["attempt"],
        }

        if check_result:
            payload["output"] = getattr(check_result, "output", "")[:500]
            payload["error"] = getattr(check_result, "error", "")

        if method == "file" or method == "all":
            self._notify_file(payload)

        if method == "webhook" or method == "all":
            webhook_url = entry.get("notification", {}).get("webhookUrl", "")
            if webhook_url:
                success = self._notify_webhook(webhook_url, payload)
                if not success and method == "webhook":
                    # Fallback to file on webhook exhaustion
                    payload["_webhook_fallback"] = True
                    self._notify_file(payload)

        if method == "slack" or method == "all":
            slack_url = entry.get("notification", {}).get("slackWebhookUrl", "")
            if slack_url:
                success = self._notify_slack(slack_url, payload)
                if not success and method == "slack":
                    payload["_slack_fallback"] = True
                    self._notify_file(payload)

        if method == "telegram" or method == "all":
            bot_token = entry.get("notification", {}).get("telegramBotToken", "")
            chat_id = entry.get("notification", {}).get("telegramChatId", "")
            if bot_token and chat_id:
                success = self._notify_telegram(bot_token, chat_id, payload)
                if not success and method == "telegram":
                    payload["_telegram_fallback"] = True
                    self._notify_file(payload)

        if method == "discord" or method == "all":
            discord_url = entry.get("notification", {}).get("discordWebhookUrl", "")
            if discord_url:
                success = self._notify_discord(discord_url, payload)
                if not success and method == "discord":
                    payload["_discord_fallback"] = True
                    self._notify_file(payload)

        if method == "teams" or method == "all":
            teams_url = entry.get("notification", {}).get("teamsWebhookUrl", "")
            if teams_url:
                success = self._notify_teams(teams_url, payload)
                if not success and method == "teams":
                    payload["_teams_fallback"] = True
                    self._notify_file(payload)

        if method == "ntfy" or method == "all":
            ntfy_server = entry.get("notification", {}).get("ntfyServer", "")
            ntfy_topic = entry.get("notification", {}).get("ntfyTopic", "")
            if ntfy_server and ntfy_topic:
                success = self._notify_ntfy(ntfy_server, ntfy_topic, payload)
                if not success and method == "ntfy":
                    payload["_ntfy_fallback"] = True
                    self._notify_file(payload)

        if method == "pushover" or method == "all":
            pushover_user = entry.get("notification", {}).get("pushoverUserKey", "")
            pushover_token = entry.get("notification", {}).get("pushoverAppToken", "")
            if pushover_user and pushover_token:
                success = self._notify_pushover(pushover_user, pushover_token, payload)
                if not success and method == "pushover":
                    payload["_pushover_fallback"] = True
                    self._notify_file(payload)

        if method == "gotify" or method == "all":
            gotify_server = entry.get("notification", {}).get("gotifyServerUrl", "")
            gotify_token = entry.get("notification", {}).get("gotifyAppToken", "")
            if gotify_server and gotify_token:
                success = self._notify_gotify(gotify_server, gotify_token, payload)
                if not success and method == "gotify":
                    payload["_gotify_fallback"] = True
                    self._notify_file(payload)

        if method == "matrix" or method == "all":
            matrix_hs = entry.get("notification", {}).get("matrixHomeserver", "")
            matrix_token = entry.get("notification", {}).get("matrixAccessToken", "")
            matrix_room = entry.get("notification", {}).get("matrixRoomId", "")
            if matrix_hs and matrix_token and matrix_room:
                success = self._notify_matrix(matrix_hs, matrix_token, matrix_room, payload)
                if not success and method == "matrix":
                    payload["_matrix_fallback"] = True
                    self._notify_file(payload)

        if method == "twilio_sms" or method == "all":
            twilio_sid = entry.get("notification", {}).get("twilioAccountSid", "")
            twilio_token = entry.get("notification", {}).get("twilioAuthToken", "")
            twilio_from = entry.get("notification", {}).get("twilioFromNumber", "")
            twilio_to = entry.get("notification", {}).get("twilioToNumber", "")
            if twilio_sid and twilio_token and twilio_from and twilio_to:
                success = self._notify_twilio_sms(twilio_sid, twilio_token, twilio_from, twilio_to, payload)
                if not success and method == "twilio_sms":
                    payload["_twilio_sms_fallback"] = True
                    self._notify_file(payload)

        if method == "google_chat" or method == "all":
            google_chat_url = entry.get("notification", {}).get("googleChatWebhookUrl", "")
            if google_chat_url:
                success = self._notify_google_chat(google_chat_url, payload)
                if not success and method == "google_chat":
                    payload["_google_chat_fallback"] = True
                    self._notify_file(payload)

        if method == "email" or method == "all":
            smtp_config = {
                "server": entry.get("notification", {}).get("smtpServer", ""),
                "port": entry.get("notification", {}).get("smtpPort", 587),
                "username": entry.get("notification", {}).get("smtpUsername", ""),
                "password": entry.get("notification", {}).get("smtpPassword", ""),
                "from_addr": entry.get("notification", {}).get("smtpFrom", ""),
                "to_addr": entry.get("notification", {}).get("smtpTo", ""),
                "use_tls": entry.get("notification", {}).get("smtpUseTls", True),
            }
            if smtp_config["server"] and smtp_config["from_addr"] and smtp_config["to_addr"]:
                success = self._notify_email(smtp_config, payload)
                if not success and method == "email":
                    payload["_email_fallback"] = True
                    self._notify_file(payload)

        # Always log to stderr
        self._notify_stderr(payload)

    def _notify_file(self, payload: dict):
        """Append JSONL to notifications file, rotating if over size limit."""
        try:
            self._maybe_rotate()
            with open(self.notifications_file, "a") as f:
                f.write(json.dumps(payload) + "\n")
        except IOError as e:
            print(f"[gen-loop] File notification error: {e}", file=sys.stderr, flush=True)

    def _maybe_rotate(self):
        """Rotate notifications.jsonl → .jsonl.1 when exceeding size limit."""
        try:
            if self.notifications_file.exists() and self.notifications_file.stat().st_size > ROTATION_SIZE_BYTES:
                rotated = self.notifications_file.with_suffix(".jsonl.1")
                if rotated.exists():
                    rotated.unlink()
                self.notifications_file.rename(rotated)
        except IOError:
            pass  # Best-effort rotation

    def _notify_slack(self, url: str, payload: dict) -> bool:
        """POST Slack Block Kit message to webhook URL with retry."""
        slack_payload = self._build_slack_blocks(payload)
        return self._notify_webhook(url, slack_payload)

    def _notify_telegram(self, bot_token: str, chat_id: str, payload: dict) -> bool:
        """POST HTML message to Telegram Bot API with retry."""
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        telegram_payload = {
            "chat_id": chat_id,
            "text": self._build_telegram_message(payload),
            "parse_mode": "HTML",
        }
        return self._notify_webhook(url, telegram_payload)

    def _notify_discord(self, url: str, payload: dict) -> bool:
        """POST Discord embed message to webhook URL with retry."""
        discord_payload = self._build_discord_embed(payload)
        return self._notify_webhook(url, discord_payload)

    @staticmethod
    def _build_discord_embed(payload: dict) -> dict:
        """Build Discord embed message from notification payload."""
        color_map = {
            "completed": 0x2ECC71,   # green
            "failed": 0xE74C3C,      # red
            "expired": 0xF39C12,     # orange
            "retry": 0x3498DB,       # blue
            "cancelled": 0x95A5A6,   # grey
        }
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()
        color = color_map.get(payload["event"], 0x7F8C8D)

        embed = {
            "title": f"{emoji} Loop {status_text}",
            "color": color,
            "fields": [
                {"name": "Loop", "value": f"`{payload['loop_id']}`", "inline": True},
                {"name": "Status", "value": status_text, "inline": True},
                {"name": "Task", "value": payload["task"], "inline": False},
                {"name": "Attempts", "value": str(payload["attempts"]), "inline": True},
            ],
            "footer": {"text": f"gen-loop-mcp | {payload['timestamp']}"},
        }

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            embed["description"] = f"```\n{context_text[:500]}\n```"

        return {"embeds": [embed]}

    @staticmethod
    def _build_telegram_message(payload: dict) -> str:
        """Build HTML-formatted Telegram message from notification payload."""
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()

        task_escaped = html.escape(str(payload["task"]))
        loop_id_escaped = html.escape(str(payload["loop_id"]))

        lines = [
            f"{emoji} <b>Loop {status_text}</b>",
            "",
            f"<b>Loop:</b> <code>{loop_id_escaped}</code>",
            f"<b>Status:</b> {status_text}",
            f"<b>Task:</b> {task_escaped}",
            f"<b>Attempts:</b> {payload['attempts']}",
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            lines.append("")
            lines.append(f"<b>Output:</b>\n<pre>{html.escape(str(context_text)[:500])}</pre>")

        lines.append("")
        lines.append(f"<i>gen-loop-mcp | {payload['timestamp']}</i>")

        return "\n".join(lines)

    @staticmethod
    def _build_slack_blocks(payload: dict) -> dict:
        """Build Slack Block Kit message from notification payload."""
        emoji_map = {
            "completed": ":white_check_mark:",
            "failed": ":x:",
            "expired": ":alarm_clock:",
            "retry": ":arrows_counterclockwise:",
            "cancelled": ":no_entry_sign:",
        }
        emoji = emoji_map.get(payload["event"], ":memo:")
        status_text = payload["event"].upper()

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Loop {status_text}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Loop:*\n`{payload['loop_id']}`"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{status_text}"},
                    {"type": "mrkdwn", "text": f"*Task:*\n{payload['task']}"},
                    {"type": "mrkdwn", "text": f"*Attempts:*\n{payload['attempts']}"},
                ],
            },
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Output:*\n```{context_text[:500]}```",
                },
            })

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"gen-loop-mcp | {payload['timestamp']}"},
            ],
        })

        return {"blocks": blocks}

    def _notify_ntfy(self, server: str, topic: str, payload: dict) -> bool:
        """POST JSON message to ntfy.sh server with retry."""
        ntfy_payload = self._build_ntfy_message(payload)
        ntfy_payload["topic"] = topic
        return self._notify_webhook(server, ntfy_payload)

    @staticmethod
    def _build_ntfy_message(payload: dict) -> dict:
        """Build ntfy.sh JSON message from notification payload."""
        priority_map = {
            "completed": 3,   # default
            "failed": 5,      # urgent
            "expired": 4,     # high
            "retry": 3,       # default
            "cancelled": 2,   # low
        }
        tag_map = {
            "completed": "white_check_mark",
            "failed": "x",
            "expired": "alarm_clock",
            "retry": "arrows_counterclockwise",
            "cancelled": "no_entry_sign",
        }
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()
        priority = priority_map.get(payload["event"], 3)
        tag = tag_map.get(payload["event"], "memo")

        message_lines = [
            f"Loop: {payload['loop_id']}",
            f"Task: {payload['task']}",
            f"Attempts: {payload['attempts']}",
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            message_lines.append(f"Output: {context_text[:500]}")

        return {
            "title": f"{emoji} Loop {status_text}",
            "message": "\n".join(message_lines),
            "priority": priority,
            "tags": [tag, "loop"],
        }

    def _notify_pushover(self, user_key: str, app_token: str, payload: dict) -> bool:
        """POST JSON message to Pushover API with retry."""
        pushover_payload = self._build_pushover_message(payload, user_key, app_token)
        return self._notify_webhook("https://api.pushover.net/1/messages.json", pushover_payload)

    @staticmethod
    def _build_pushover_message(payload: dict, user_key: str, app_token: str) -> dict:
        """Build Pushover JSON message from notification payload."""
        priority_map = {
            "completed": -1,   # low
            "failed": 1,       # high
            "expired": 0,      # normal
            "retry": 0,        # normal
            "cancelled": -1,   # low
        }
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()
        priority = priority_map.get(payload["event"], 0)

        message_lines = [
            f"Loop: {payload['loop_id']}",
            f"Task: {payload['task']}",
            f"Attempts: {payload['attempts']}",
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            message_lines.append(f"Output: {context_text[:500]}")

        return {
            "token": app_token,
            "user": user_key,
            "title": f"{emoji} Loop {status_text}",
            "message": "\n".join(message_lines),
            "priority": priority,
        }

    def _notify_gotify(self, server_url: str, app_token: str, payload: dict) -> bool:
        """POST JSON message to Gotify server with retry."""
        url = f"{server_url.rstrip('/')}/message?token={app_token}"
        gotify_payload = self._build_gotify_message(payload)
        return self._notify_webhook(url, gotify_payload)

    @staticmethod
    def _build_gotify_message(payload: dict) -> dict:
        """Build Gotify JSON message from notification payload."""
        priority_map = {
            "completed": 2,    # low
            "failed": 8,       # high
            "expired": 5,      # normal
            "retry": 5,        # normal
            "cancelled": 2,    # low
        }
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()
        priority = priority_map.get(payload["event"], 5)

        message_lines = [
            f"Loop: {payload['loop_id']}",
            f"Task: {payload['task']}",
            f"Attempts: {payload['attempts']}",
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            message_lines.append(f"Output: {context_text[:500]}")

        return {
            "title": f"{emoji} Loop {status_text}",
            "message": "\n".join(message_lines),
            "priority": priority,
        }

    def _notify_matrix(self, homeserver: str, access_token: str, room_id: str, payload: dict) -> bool:
        """PUT message to Matrix room via Client-Server API with retry.

        Uses PUT /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}
        with Bearer token auth in header.
        """
        import uuid
        txn_id = uuid.uuid4().hex
        url = f"{homeserver.rstrip('/')}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"
        matrix_payload = self._build_matrix_message(payload)
        delays = [0, 1, 2]
        for i, delay in enumerate(delays):
            if delay > 0:
                time.sleep(delay)
            try:
                data = json.dumps(matrix_payload).encode("utf-8")
                req = urllib.request.Request(
                    url, data=data, method="PUT",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {access_token}",
                        "User-Agent": f"gen-loop-mcp/{__version__}",
                    },
                )
                urllib.request.urlopen(req, timeout=5)
                return True
            except Exception as e:
                attempt_label = f"attempt {i + 1}/{len(delays)}"
                print(f"[gen-loop] Matrix error ({homeserver}, {attempt_label}): {e}", file=sys.stderr, flush=True)
        return False

    @staticmethod
    def _build_matrix_message(payload: dict) -> dict:
        """Build Matrix m.room.message event from notification payload."""
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()

        plain_lines = [
            f"{emoji} Loop {status_text}",
            "",
            f"Loop: {payload['loop_id']}",
            f"Task: {payload['task']}",
            f"Attempts: {payload['attempts']}",
        ]

        html_lines = [
            f"<h4>{emoji} Loop {status_text}</h4>",
            "<ul>",
            f"<li><b>Loop:</b> <code>{payload['loop_id']}</code></li>",
            f"<li><b>Task:</b> {payload['task']}</li>",
            f"<li><b>Attempts:</b> {payload['attempts']}</li>",
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            truncated = context_text[:500]
            plain_lines.append(f"Output: {truncated}")
            html_lines.append(f"<li><b>Output:</b> <pre>{truncated}</pre></li>")

        html_lines.append("</ul>")
        plain_lines.append("")
        plain_lines.append(f"gen-loop-mcp | {payload['timestamp']}")
        html_lines.append(f"<sub>gen-loop-mcp | {payload['timestamp']}</sub>")

        return {
            "msgtype": "m.text",
            "body": "\n".join(plain_lines),
            "format": "org.matrix.custom.html",
            "formatted_body": "\n".join(html_lines),
        }

    def _notify_twilio_sms(
        self, account_sid: str, auth_token: str, from_number: str, to_number: str, payload: dict
    ) -> bool:
        """POST form-encoded message to Twilio SMS API with retry.

        Uses POST /2010-04-01/Accounts/{AccountSid}/Messages
        with Basic auth (base64 AccountSid:AuthToken).
        """
        import base64
        import urllib.parse
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages"
        sms_body = self._build_twilio_sms_message(payload)
        form_data = urllib.parse.urlencode({
            "To": to_number,
            "From": from_number,
            "Body": sms_body,
        }).encode("utf-8")
        credentials = f"{account_sid}:{auth_token}".encode("utf-8")
        auth_header = f"Basic {base64.b64encode(credentials).decode('utf-8')}"
        delays = [0, 1, 2]
        for i, delay in enumerate(delays):
            if delay > 0:
                time.sleep(delay)
            try:
                req = urllib.request.Request(
                    url, data=form_data, method="POST",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": auth_header,
                        "User-Agent": f"gen-loop-mcp/{__version__}",
                    },
                )
                urllib.request.urlopen(req, timeout=5)
                return True
            except Exception as e:
                attempt_label = f"attempt {i + 1}/{len(delays)}"
                print(f"[gen-loop] Twilio SMS error ({to_number}, {attempt_label}): {e}", file=sys.stderr, flush=True)
        return False

    @staticmethod
    def _build_twilio_sms_message(payload: dict) -> str:
        """Build plain-text SMS message from notification payload."""
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()

        lines = [
            f"{emoji} Loop {status_text}",
            f"Loop: {payload['loop_id']}",
            f"Task: {payload['task']}",
            f"Attempts: {payload['attempts']}",
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            lines.append(f"Output: {context_text[:100]}")

        return "\n".join(lines)

    def _notify_google_chat(self, url: str, payload: dict) -> bool:
        """POST Cards v2 message to Google Chat webhook URL with retry."""
        card_payload = self._build_google_chat_card(payload)
        return self._notify_webhook(url, card_payload)

    @staticmethod
    def _build_google_chat_card(payload: dict) -> dict:
        """Build Google Chat Cards v2 message from notification payload."""
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()

        widgets = [
            {
                "decoratedText": {
                    "topLabel": "Task",
                    "text": payload["task"],
                },
            },
            {
                "decoratedText": {
                    "topLabel": "Status",
                    "text": status_text,
                },
            },
            {
                "decoratedText": {
                    "topLabel": "Attempts",
                    "text": str(payload["attempts"]),
                },
            },
        ]

        sections = [{"widgets": widgets}]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            sections.append({
                "header": "Output",
                "collapsible": True,
                "widgets": [
                    {
                        "textParagraph": {
                            "text": context_text[:500],
                        },
                    },
                ],
            })

        sections.append({
            "widgets": [
                {
                    "textParagraph": {
                        "text": f"<i>gen-loop-mcp | {payload['timestamp']}</i>",
                    },
                },
            ],
        })

        return {
            "cardsV2": [
                {
                    "cardId": f"loop-{payload['loop_id']}",
                    "card": {
                        "header": {
                            "title": f"{emoji} Loop {status_text}",
                            "subtitle": payload["loop_id"],
                        },
                        "sections": sections,
                    },
                },
            ],
        }

    def _notify_teams(self, url: str, payload: dict) -> bool:
        """POST Adaptive Card message to Teams Workflow webhook URL with retry."""
        teams_payload = self._build_teams_card(payload)
        return self._notify_webhook(url, teams_payload)

    @staticmethod
    def _build_teams_card(payload: dict) -> dict:
        """Build Teams Adaptive Card message from notification payload."""
        style_map = {
            "completed": "good",
            "failed": "attention",
            "expired": "warning",
            "retry": "accent",
            "cancelled": "default",
        }
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()
        style = style_map.get(payload["event"], "default")

        body = [
            {
                "type": "Container",
                "style": style,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"{emoji} Loop {status_text}",
                        "size": "Large",
                        "weight": "Bolder",
                    },
                ],
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Loop", "value": payload["loop_id"]},
                    {"title": "Status", "value": status_text},
                    {"title": "Task", "value": payload["task"]},
                    {"title": "Attempts", "value": str(payload["attempts"])},
                ],
            },
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            body.append({
                "type": "TextBlock",
                "text": context_text[:500],
                "fontType": "Monospace",
                "wrap": True,
            })

        body.append({
            "type": "TextBlock",
            "text": f"gen-loop-mcp | {payload['timestamp']}",
            "size": "Small",
            "isSubtle": True,
        })

        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
            "body": body,
        }

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": card,
                }
            ],
        }

    def _notify_email(self, config: dict, payload: dict) -> bool:
        """Send email via SMTP with retry (2 retries, 1s/2s backoff).

        Returns True if any attempt succeeds, False if all fail.
        """
        delays = [0, 1, 2]  # Initial attempt, then 1s, then 2s backoff
        for i, delay in enumerate(delays):
            if delay > 0:
                time.sleep(delay)
            try:
                to_addrs = [addr.strip() for addr in config["to_addr"].split(",")]
                message = self._build_email_message(payload, config["from_addr"], config["to_addr"])
                if config.get("use_tls", True):
                    context = ssl.create_default_context()
                    with smtplib.SMTP(config["server"], config["port"], timeout=5) as server:
                        server.starttls(context=context)
                        if config.get("username") and config.get("password"):
                            server.login(config["username"], config["password"])
                        server.sendmail(config["from_addr"], to_addrs, message)
                else:
                    with smtplib.SMTP(config["server"], config["port"], timeout=5) as server:
                        if config.get("username") and config.get("password"):
                            server.login(config["username"], config["password"])
                        server.sendmail(config["from_addr"], to_addrs, message)
                return True
            except Exception as e:
                attempt_label = f"attempt {i + 1}/{len(delays)}"
                print(f"[gen-loop] Email error ({config['server']}:{config['port']}, {attempt_label}): {e}",
                      file=sys.stderr, flush=True)
        return False

    @staticmethod
    def _build_email_message(payload: dict, from_addr: str, to_addr: str) -> str:
        """Build plain-text MIME email from notification payload."""
        emoji_map = {
            "completed": "\u2705",
            "failed": "\u274c",
            "expired": "\u23f0",
            "retry": "\U0001f504",
            "cancelled": "\U0001f6ab",
        }
        emoji = emoji_map.get(payload["event"], "\U0001f4dd")
        status_text = payload["event"].upper()

        subject = f"{emoji} Loop {status_text}: {payload['loop_id']}"

        body_lines = [
            f"Loop ID: {payload['loop_id']}",
            f"Event: {status_text}",
            f"Task: {payload['task']}",
            f"Status: {payload.get('status', 'unknown')}",
            f"Attempts: {payload['attempts']}",
            f"Time: {payload['timestamp']}",
        ]

        output = payload.get("output", "")
        error = payload.get("error", "")
        context_text = output or error
        if context_text:
            body_lines.append("")
            body_lines.append(f"Output:\n{context_text[:500]}")

        body_lines.append("")
        body_lines.append("---")
        body_lines.append("gen-loop-mcp")

        msg = MIMEText("\n".join(body_lines))
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        return msg.as_string()

    def _notify_webhook(self, url: str, payload: dict) -> bool:
        """POST JSON to webhook URL with retry (2 retries, 1s/2s backoff).

        Returns True if any attempt succeeds, False if all fail.
        """
        delays = [0, 1, 2]  # Initial attempt, then 1s, then 2s backoff
        for i, delay in enumerate(delays):
            if delay > 0:
                time.sleep(delay)
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url, data=data, method="POST",
                    headers={"Content-Type": "application/json", "User-Agent": f"gen-loop-mcp/{__version__}"},
                )
                urllib.request.urlopen(req, timeout=5)
                return True
            except Exception as e:
                attempt_label = f"attempt {i + 1}/{len(delays)}"
                print(f"[gen-loop] Webhook error ({url}, {attempt_label}): {e}", file=sys.stderr, flush=True)
        return False

    @staticmethod
    def _notify_stderr(payload: dict):
        """Structured log to stderr."""
        emoji = {"completed": "✅", "failed": "❌", "expired": "⏰", "retry": "🔄", "cancelled": "🚫"}.get(
            payload["event"], "📝"
        )
        print(
            f"[gen-loop] {emoji} {payload['loop_id']} {payload['event']}: {payload['task']}",
            file=sys.stderr, flush=True,
        )
