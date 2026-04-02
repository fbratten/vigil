"""Tests for the internal scheduler thread."""

import time
import threading
import unittest.mock
import pytest
from datetime import datetime, timezone, timedelta
from gen_loop.store import LoopStore
from gen_loop.scheduler import SchedulerThread


@pytest.fixture
def store(tmp_path):
    return LoopStore(tmp_path / "loop-store")


class TestSchedulerFiring:
    def test_fires_due_check(self, store):
        """Schedule a loop with immediate check, verify it completes."""
        events = []

        def on_event(entry, event_type, result):
            events.append((entry["id"], event_type))

        # Create loop that's already due (0 minute delay → nextCheckAt in the past)
        entry = store.create(task="Immediate check", check_command="echo works",
                             success_criteria="works", check_after_minutes=0)

        sched = SchedulerThread(store=store, poll_interval=0.5, on_event=on_event)
        sched.start()
        time.sleep(2)  # Give scheduler time to poll and fire
        sched.stop()
        sched.join(timeout=3)

        final = store.get(entry["id"])
        assert final["status"] == "completed"
        assert any(eid == entry["id"] and etype == "completed" for eid, etype in events)

    def test_retries_on_failure(self, store):
        """Failing check should retry."""
        entry = store.create(task="Will fail", check_command="false",
                             check_after_minutes=0, max_retries=2,
                             retry_backoff_minutes=[0])  # Immediate retry

        sched = SchedulerThread(store=store, poll_interval=0.5)
        sched.start()
        time.sleep(3)
        sched.stop()
        sched.join(timeout=3)

        final = store.get(entry["id"])
        assert final["status"] == "failed"
        assert final["state"]["attempt"] >= 2

    def test_expires_overdue(self, store):
        """Loop past expiry should be marked expired."""
        entry = store.create(task="Expired", check_command="echo hi",
                             check_after_minutes=0, expires_after_hours=0)

        sched = SchedulerThread(store=store, poll_interval=0.5)
        sched.start()
        time.sleep(2)
        sched.stop()
        sched.join(timeout=3)

        final = store.get(entry["id"])
        assert final["status"] == "expired"


class TestRecovery:
    def test_recovers_overdue_on_startup(self, store):
        """Loops with past nextCheckAt should fire on scheduler start."""
        # Create loop with nextCheckAt in the past
        entry = store.create(task="Overdue", check_command="echo recovered",
                             success_criteria="recovered", check_after_minutes=0)

        # Manually set nextCheckAt to the past
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        store.set_next_check(entry["id"], past)

        sched = SchedulerThread(store=store, poll_interval=0.5)
        sched.start()
        time.sleep(2)
        sched.stop()
        sched.join(timeout=3)

        final = store.get(entry["id"])
        assert final["status"] == "completed"


class TestConcurrency:
    def test_max_concurrent_respected(self, store):
        """With max_concurrent=3, at most 3 checks run simultaneously."""

        peak = {"value": 0}
        current = {"value": 0}
        lock = threading.Lock()
        original_run_check = SchedulerThread._run_check

        def slow_run_check(self_sched, entry):
            with lock:
                current["value"] += 1
                if current["value"] > peak["value"]:
                    peak["value"] = current["value"]
            time.sleep(0.5)
            with lock:
                current["value"] -= 1
            original_run_check(self_sched, entry)

        # Create 8 loops all due immediately
        for i in range(8):
            store.create(task=f"Concurrent {i}", check_command="echo ok",
                         success_criteria="ok", check_after_minutes=0)

        sched = SchedulerThread(store=store, poll_interval=0.3, max_concurrent=3)

        with unittest.mock.patch.object(SchedulerThread, "_run_check", slow_run_check):
            sched.start()
            time.sleep(4)
            sched.stop()
            sched.join(timeout=3)

        assert peak["value"] <= 3


class TestStopClean:
    def test_stops_cleanly(self, store):
        """Scheduler should stop without hanging."""
        sched = SchedulerThread(store=store, poll_interval=0.5)
        sched.start()
        assert sched.is_alive()
        sched.stop()
        sched.join(timeout=3)
        assert not sched.is_alive()
