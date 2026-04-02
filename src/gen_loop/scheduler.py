"""Internal scheduler thread — polls store and fires checks autonomously."""

import sys
import threading
from datetime import datetime, timezone, timedelta

from gen_loop.checks import run_check
from gen_loop.store import LoopStore


class SchedulerThread(threading.Thread):
    """Background daemon thread that polls the store and fires checks.

    Runs every `poll_interval` seconds, finds active loops with
    nextCheckAt <= now, and runs their checks. Handles retry, backoff,
    expiry, and recovery on startup.
    """

    def __init__(
        self,
        store: LoopStore,
        poll_interval: float = 10.0,
        on_event: callable = None,
        max_concurrent: int = 5,
    ):
        super().__init__(daemon=True, name="gen-loop-scheduler")
        self.store = store
        self.poll_interval = poll_interval
        self.on_event = on_event  # Callback: on_event(loop_entry, event_type, result)
        self._stop_event = threading.Event()
        self._semaphore = threading.Semaphore(max_concurrent)

    def run(self):
        """Main loop — poll and fire until stopped."""
        self._log("Scheduler started")
        self._recover()
        while not self._stop_event.is_set():
            try:
                self._poll_and_fire()
            except Exception as e:
                self._log(f"Scheduler error: {e}")
            self._stop_event.wait(self.poll_interval)
        self._log("Scheduler stopped")

    def stop(self):
        """Signal the scheduler to stop."""
        self._stop_event.set()

    def _recover(self):
        """On startup, handle overdue loops."""
        now = datetime.now(timezone.utc)
        active = self.store.list_all(status="active")
        recovered = 0

        for entry in active:
            # Check expiry first
            expires_at = entry["schedule"].get("expiresAt")
            if expires_at:
                try:
                    exp = datetime.fromisoformat(expires_at)
                    if now > exp:
                        self.store.set_status(entry["id"], "expired")
                        self.store.add_history(entry["id"], result="expired", note="Expired during downtime")
                        self._emit(entry, "expired", None)
                        continue
                except (ValueError, TypeError):
                    pass

            # Check if overdue
            next_check = entry["state"].get("nextCheckAt")
            if next_check:
                try:
                    nxt = datetime.fromisoformat(next_check)
                    if now > nxt:
                        recovered += 1
                        # Fire immediately in a sub-thread
                        threading.Thread(
                            target=self._run_check_guarded,
                            args=(entry,),
                            daemon=True,
                        ).start()
                except (ValueError, TypeError):
                    pass

        if recovered:
            self._log(f"Recovered {recovered} overdue loop(s)")

    def _poll_and_fire(self):
        """Find active loops that are due and fire them."""
        now = datetime.now(timezone.utc)
        active = self.store.list_all(status="active")

        for entry in active:
            next_check = entry["state"].get("nextCheckAt")
            if not next_check:
                continue
            try:
                nxt = datetime.fromisoformat(next_check)
                if now >= nxt:
                    threading.Thread(
                        target=self._run_check_guarded,
                        args=(entry,),
                        daemon=True,
                    ).start()
            except (ValueError, TypeError):
                continue

    def _run_check_guarded(self, entry: dict):
        """Acquire semaphore, run check, release. Used as thread target."""
        if not self._semaphore.acquire(timeout=60):
            self._log(f"Semaphore timeout for {entry['id']}, skipping this cycle")
            return
        try:
            self._run_check(entry)
        finally:
            self._semaphore.release()

    def _run_check(self, entry: dict):
        """Execute a check for a loop and handle the result."""
        loop_id = entry["id"]

        # Re-read to avoid stale data
        entry = self.store.get(loop_id)
        if entry is None or entry["status"] != "active":
            return

        # Check expiry
        expires_at = entry["schedule"].get("expiresAt")
        if expires_at:
            try:
                now = datetime.now(timezone.utc)
                if now > datetime.fromisoformat(expires_at):
                    self.store.set_status(loop_id, "expired")
                    self.store.add_history(loop_id, result="expired", note="Loop expired")
                    self._emit(entry, "expired", None)
                    return
            except (ValueError, TypeError):
                pass

        # Run the check
        check = entry["check"]
        result = run_check(
            check_type=check["type"],
            command=check["command"],
            success_criteria=check.get("successCriteria", ""),
        )

        if result.success:
            self.store.add_history(loop_id, result="success", output=result.output, note="Check passed")
            self.store.set_status(loop_id, "completed")
            self._emit(entry, "completed", result)
            self._log(f"Loop {loop_id} completed: {entry['task']}")
            return

        # Failure
        attempt = entry["state"]["attempt"] + 1
        max_retries = entry["schedule"]["maxRetries"]

        self.store.add_history(
            loop_id,
            result="failure",
            output=result.output or result.error,
            note=f"Attempt {attempt}/{max_retries}",
        )

        if attempt >= max_retries:
            self.store.set_status(loop_id, "failed")
            self._emit(entry, "failed", result)
            self._log(f"Loop {loop_id} failed after {attempt} attempts: {entry['task']}")
            return

        # Reschedule with backoff
        backoff_list = entry["schedule"].get("retryBackoffMs", [300000])
        backoff_idx = min(attempt - 1, len(backoff_list) - 1)
        next_delay_ms = backoff_list[backoff_idx]

        next_check_at = (datetime.now(timezone.utc) + timedelta(milliseconds=next_delay_ms)).isoformat()
        self.store.set_next_check(loop_id, next_check_at)

        self._emit(entry, "retry", result)
        self._log(f"Loop {loop_id} retry {attempt}/{max_retries}, next in {next_delay_ms // 1000}s")

    def _emit(self, entry: dict, event_type: str, result):
        """Notify via callback if registered."""
        if self.on_event:
            try:
                self.on_event(entry, event_type, result)
            except Exception as e:
                self._log(f"Notification error: {e}")

    @staticmethod
    def _log(msg: str):
        """Log to stderr (visible to MCP clients)."""
        print(f"[gen-loop] {msg}", file=sys.stderr, flush=True)
