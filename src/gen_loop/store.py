"""Thread-safe file-based JSON store for loop entries."""

import fcntl
import json
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


class LoopStore:
    """Manages loop entries as JSON files with fcntl locking for thread safety."""

    def __init__(self, store_dir: str | Path):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._lockfile = self.store_dir / ".store.lock"
        self._thread_lock = __import__("threading").Lock()

    def _loop_path(self, loop_id: str) -> Path:
        return self.store_dir / f"{loop_id}.json"

    def _next_id(self) -> str:
        existing = [f.stem for f in self.store_dir.glob("loop-*.json")]
        if not existing:
            return "loop-001"
        numbers = []
        for name in existing:
            match = re.match(r"loop-(\d+)", name)
            if match:
                numbers.append(int(match.group(1)))
        return f"loop-{max(numbers, default=0) + 1:03d}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _acquire_lock(self):
        """Acquire thread lock + file lock for cross-process + cross-thread safety."""
        self._thread_lock.acquire()
        self._lock_fd = open(self._lockfile, "w")
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)

    def _release_lock(self):
        """Release file lock + thread lock."""
        try:
            if hasattr(self, "_lock_fd") and self._lock_fd and not self._lock_fd.closed:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()
        finally:
            self._thread_lock.release()

    def create(
        self,
        task: str,
        check_type: str = "shell",
        check_command: str = "",
        success_criteria: str = "",
        context: dict[str, Any] | None = None,
        check_after_minutes: int = 5,
        max_retries: int = 3,
        retry_backoff_minutes: list[int] | None = None,
        expires_after_hours: int = 24,
        notify_method: str = "file",
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
    ) -> dict[str, Any]:
        """Create a new loop entry (thread-safe)."""
        self._acquire_lock()
        try:
            loop_id = self._next_id()
            now = self._now_iso()

            if retry_backoff_minutes is None:
                retry_backoff_minutes = [5, 15, 60]

            expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_after_hours)).isoformat()
            next_check = (datetime.now(timezone.utc) + timedelta(minutes=check_after_minutes)).isoformat()

            entry = {
                "id": loop_id,
                "version": 1,
                "created": now,
                "updated": now,
                "status": "active",
                "task": task,
                "check": {
                    "type": check_type,
                    "command": check_command,
                    "successCriteria": success_criteria,
                },
                "context": context or {},
                "schedule": {
                    "checkAfterMs": check_after_minutes * 60 * 1000,
                    "maxRetries": max_retries,
                    "retryBackoffMs": [m * 60 * 1000 for m in retry_backoff_minutes],
                    "expiresAt": expires_at,
                },
                "state": {
                    "attempt": 0,
                    "nextCheckAt": next_check,
                    "history": [],
                },
                "notification": {
                    "method": notify_method,
                    "webhookUrl": webhook_url,
                    "slackWebhookUrl": slack_webhook_url,
                    "telegramBotToken": telegram_bot_token,
                    "telegramChatId": telegram_chat_id,
                    "discordWebhookUrl": discord_webhook_url,
                    "teamsWebhookUrl": teams_webhook_url,
                    "ntfyServer": ntfy_server,
                    "ntfyTopic": ntfy_topic,
                    "pushoverUserKey": pushover_user_key,
                    "pushoverAppToken": pushover_app_token,
                    "gotifyServerUrl": gotify_server_url,
                    "gotifyAppToken": gotify_app_token,
                    "matrixHomeserver": matrix_homeserver,
                    "matrixAccessToken": matrix_access_token,
                    "matrixRoomId": matrix_room_id,
                    "twilioAccountSid": twilio_account_sid,
                    "twilioAuthToken": twilio_auth_token,
                    "twilioFromNumber": twilio_from_number,
                    "twilioToNumber": twilio_to_number,
                    "googleChatWebhookUrl": google_chat_webhook_url,
                    "smtpServer": smtp_server,
                    "smtpPort": smtp_port,
                    "smtpUsername": smtp_username,
                    "smtpPassword": smtp_password,
                    "smtpFrom": smtp_from,
                    "smtpTo": smtp_to,
                    "smtpUseTls": smtp_use_tls,
                    "filePath": "",
                },
            }

            self._write_atomic(loop_id, entry)
            return entry
        finally:
            self._release_lock()

    def get(self, loop_id: str) -> dict[str, Any] | None:
        """Read a loop entry (no lock needed — atomic writes)."""
        path = self._loop_path(loop_id)
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def update(self, loop_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Merge updates into existing entry (thread-safe)."""
        self._acquire_lock()
        try:
            entry = self.get(loop_id)
            if entry is None:
                return None
            self._deep_merge(entry, updates)
            entry["updated"] = self._now_iso()
            self._write_atomic(loop_id, entry)
            return entry
        finally:
            self._release_lock()

    def delete(self, loop_id: str) -> bool:
        """Delete a loop entry (thread-safe)."""
        self._acquire_lock()
        try:
            path = self._loop_path(loop_id)
            if path.exists():
                path.unlink()
                return True
            return False
        finally:
            self._release_lock()

    def list_all(self, status: str | None = None) -> list[dict[str, Any]]:
        """List all entries, optionally filtered by status."""
        entries = []
        for path in sorted(self.store_dir.glob("loop-*.json")):
            try:
                with open(path) as f:
                    entry = json.load(f)
                if status is None or entry.get("status") == status:
                    entries.append(entry)
            except (json.JSONDecodeError, IOError):
                continue  # Skip corrupt files
        return entries

    def add_history(
        self, loop_id: str, result: str, output: str = "", note: str = ""
    ) -> dict[str, Any] | None:
        """Add history entry and increment attempt (thread-safe)."""
        self._acquire_lock()
        try:
            entry = self.get(loop_id)
            if entry is None:
                return None

            entry["state"]["attempt"] += 1
            entry["state"]["history"].append({
                "attempt": entry["state"]["attempt"],
                "at": self._now_iso(),
                "result": result,
                "output": output[:2000],
                "note": note,
            })
            entry["updated"] = self._now_iso()
            self._write_atomic(loop_id, entry)
            return entry
        finally:
            self._release_lock()

    def set_status(self, loop_id: str, status: str) -> dict[str, Any] | None:
        """Update loop status (thread-safe)."""
        return self.update(loop_id, {"status": status})

    def set_next_check(self, loop_id: str, next_check_at: str) -> dict[str, Any] | None:
        """Update the next check time (thread-safe)."""
        return self.update(loop_id, {"state": {"nextCheckAt": next_check_at}})

    def _write_atomic(self, loop_id: str, entry: dict[str, Any]) -> None:
        """Write atomically: write to temp file, then rename."""
        path = self._loop_path(loop_id)
        fd, tmp_path = tempfile.mkstemp(dir=self.store_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(entry, f, indent=2)
            os.rename(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                LoopStore._deep_merge(base[key], value)
            else:
                base[key] = value
