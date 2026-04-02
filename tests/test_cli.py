"""Tests for the gen-loop-cli tool."""

import json
import pytest
from gen_loop.cli import main
from gen_loop.store import LoopStore


@pytest.fixture
def store(tmp_path):
    return LoopStore(tmp_path / "loop-store")


@pytest.fixture
def store_dir(store):
    return str(store.store_dir)


def run_cli(store_dir, *args):
    """Run CLI with store-dir override, return (stdout, stderr, exit_code)."""
    import io
    import sys

    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    exit_code = 0
    try:
        main(["--store-dir", store_dir] + list(args))
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 0
    finally:
        stdout = sys.stdout.getvalue()
        stderr = sys.stderr.getvalue()
        sys.stdout, sys.stderr = old_out, old_err
    return stdout, stderr, exit_code


class TestList:
    def test_list_empty(self, store_dir):
        out, _, _ = run_cli(store_dir, "list")
        assert "No loops found" in out

    def test_list_all(self, store, store_dir):
        store.create(task="Task A", check_command="echo a")
        store.create(task="Task B", check_command="echo b")
        out, _, _ = run_cli(store_dir, "list")
        assert "loop-001" in out
        assert "loop-002" in out
        assert "Task A" in out
        assert "Total: 2" in out

    def test_list_filter_status(self, store, store_dir):
        store.create(task="Active task")
        e2 = store.create(task="Done task")
        store.set_status(e2["id"], "completed")
        out, _, _ = run_cli(store_dir, "list", "--status", "active")
        assert "Active task" in out
        assert "Done task" not in out

    def test_list_json(self, store, store_dir):
        store.create(task="JSON test")
        out, _, _ = run_cli(store_dir, "list", "--json")
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["task"] == "JSON test"


class TestShow:
    def test_show_existing(self, store, store_dir):
        store.create(task="Show me")
        out, _, code = run_cli(store_dir, "show", "loop-001")
        assert code == 0
        assert "Show me" in out
        assert "loop-001" in out
        assert "Status:" in out

    def test_show_missing(self, store_dir):
        _, err, code = run_cli(store_dir, "show", "loop-999")
        assert code == 1
        assert "not found" in err

    def test_show_json(self, store, store_dir):
        store.create(task="JSON show")
        out, _, _ = run_cli(store_dir, "show", "loop-001", "--json")
        data = json.loads(out)
        assert data["id"] == "loop-001"
        assert data["task"] == "JSON show"


class TestDashboard:
    def test_dashboard_empty(self, store_dir):
        out, _, _ = run_cli(store_dir, "dashboard")
        assert "No loops" in out

    def test_dashboard_with_loops(self, store, store_dir):
        store.create(task="Active one")
        e2 = store.create(task="Done one")
        store.set_status(e2["id"], "completed")
        out, _, _ = run_cli(store_dir, "dashboard")
        assert "Active (1)" in out
        assert "Recent:" in out
        assert "Total: 2" in out


class TestHistory:
    def test_history_all(self, store, store_dir):
        e = store.create(task="History test", check_command="echo hi")
        store.add_history(e["id"], result="success", output="hi")
        store.add_history(e["id"], result="success", output="hi again")
        out, _, _ = run_cli(store_dir, "history")
        assert "loop-001" in out
        assert "Total: 2" in out

    def test_history_filter(self, store, store_dir):
        e1 = store.create(task="Active")
        store.add_history(e1["id"], result="pending", output="waiting")
        e2 = store.create(task="Done")
        store.set_status(e2["id"], "completed")
        store.add_history(e2["id"], result="success", output="ok")
        out, _, _ = run_cli(store_dir, "history", "--status", "completed", "--limit", "5")
        assert "loop-002" in out
        assert "loop-001" not in out


class TestCancel:
    def test_cancel_active(self, store, store_dir):
        store.create(task="Cancel me")
        out, _, code = run_cli(store_dir, "cancel", "loop-001", "--yes")
        assert code == 0
        assert "cancelled" in out
        assert store.get("loop-001")["status"] == "cancelled"

    def test_cancel_already_done(self, store, store_dir):
        e = store.create(task="Already done")
        store.set_status(e["id"], "completed")
        _, err, code = run_cli(store_dir, "cancel", "loop-001")
        assert code == 1
        assert "not active" in err


class TestBatch:
    def test_batch_summary(self, store, store_dir):
        store.create(task="Active")
        e2 = store.create(task="Done")
        store.set_status(e2["id"], "completed")
        out, _, _ = run_cli(store_dir, "batch", "summary")
        assert "Total: 2" in out
        assert "active: 1" in out
        assert "completed: 1" in out


class TestStats:
    def test_stats(self, store, store_dir):
        e1 = store.create(task="A")
        store.add_history(e1["id"], result="success")
        store.set_status(e1["id"], "completed")
        e2 = store.create(task="B")
        store.add_history(e2["id"], result="fail")
        store.set_status(e2["id"], "failed")
        out, _, _ = run_cli(store_dir, "stats")
        assert "Total loops:" in out
        assert "Success rate:" in out
        assert "50.0%" in out

    def test_stats_json(self, store, store_dir):
        store.create(task="A")
        out, _, _ = run_cli(store_dir, "stats", "--json")
        data = json.loads(out)
        assert "total" in data
        assert "by_status" in data
        assert "success_rate_pct" in data
        assert data["total"] == 1


class TestNotifications:
    """Tests for the notifications subcommand."""

    @pytest.fixture
    def notifications_file(self, store, store_dir):
        """Create sample notifications.jsonl for testing."""
        from pathlib import Path

        notif_path = Path(store_dir) / "notifications.jsonl"
        entries = [
            {
                "timestamp": "2026-02-05T10:00:00+00:00",
                "loop_id": "loop-001",
                "event": "completed",
                "task": "Test task A",
                "status": "completed",
                "attempts": 2,
            },
            {
                "timestamp": "2026-02-05T11:00:00+00:00",
                "loop_id": "loop-002",
                "event": "failed",
                "task": "Test task B",
                "status": "failed",
                "attempts": 3,
            },
            {
                "timestamp": "2026-02-05T12:00:00+00:00",
                "loop_id": "loop-001",
                "event": "retry",
                "task": "Test task A",
                "status": "active",
                "attempts": 1,
            },
        ]
        with open(notif_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return notif_path

    def test_notifications_no_file(self, store_dir):
        """No notifications.jsonl exists - shows appropriate message."""
        out, _, _ = run_cli(store_dir, "notifications")
        assert "No notifications file found" in out

    def test_notifications_empty_file(self, store, store_dir):
        """Empty file shows no notifications found."""
        from pathlib import Path

        notif_path = Path(store_dir) / "notifications.jsonl"
        notif_path.touch()
        out, _, _ = run_cli(store_dir, "notifications")
        assert "No notifications found" in out

    def test_notifications_basic(self, store, store_dir, notifications_file):
        """Basic table output with correct columns."""
        out, _, _ = run_cli(store_dir, "notifications")
        assert "TIME" in out
        assert "LOOP" in out
        assert "EVENT" in out
        assert "STATUS" in out
        assert "TASK" in out
        assert "loop-001" in out
        assert "loop-002" in out
        assert "Total: 3" in out

    def test_notifications_filter_loop_id(self, store, store_dir, notifications_file):
        """--loop-id filters correctly."""
        out, _, _ = run_cli(store_dir, "notifications", "--loop-id", "loop-001")
        assert "loop-001" in out
        assert "loop-002" not in out
        assert "Total: 2" in out  # Two entries for loop-001

    def test_notifications_filter_event(self, store, store_dir, notifications_file):
        """--event filters correctly."""
        out, _, _ = run_cli(store_dir, "notifications", "--event", "completed")
        assert "completed" in out
        assert "failed" not in out
        assert "retry" not in out
        assert "Total: 1" in out

    def test_notifications_filter_since(self, store, store_dir, notifications_file):
        """--since excludes older entries."""
        out, _, _ = run_cli(store_dir, "notifications", "--since", "2026-02-05T11:00:00")
        # Should include 11:00 and 12:00 entries
        assert "loop-002" in out  # 11:00 failed
        assert "Total: 2" in out

    def test_notifications_filter_until(self, store, store_dir, notifications_file):
        """--until excludes newer entries."""
        # Use timestamp with timezone to match data format
        out, _, _ = run_cli(store_dir, "notifications", "--until", "2026-02-05T11:30:00+00:00")
        # Should include 10:00 and 11:00 entries (excludes 12:00)
        assert "loop-001" in out  # 10:00 completed
        assert "loop-002" in out  # 11:00 failed
        assert "Total: 2" in out

    def test_notifications_limit(self, store, store_dir, notifications_file):
        """--limit caps results."""
        out, _, _ = run_cli(store_dir, "notifications", "--limit", "2")
        assert "Total: 2" in out

    def test_notifications_include_rotated(self, store, store_dir, notifications_file):
        """--include-rotated reads both files."""
        from pathlib import Path

        # Create rotated file with older entry
        rotated_path = Path(store_dir) / "notifications.jsonl.1"
        old_entry = {
            "timestamp": "2026-02-04T10:00:00+00:00",
            "loop_id": "loop-old",
            "event": "expired",
            "task": "Old task",
            "status": "expired",
            "attempts": 5,
        }
        with open(rotated_path, "w") as f:
            f.write(json.dumps(old_entry) + "\n")

        # Without --include-rotated, old entry not shown
        out, _, _ = run_cli(store_dir, "notifications")
        assert "loop-old" not in out
        assert "Total: 3" in out

        # With --include-rotated, old entry is shown
        out, _, _ = run_cli(store_dir, "notifications", "--include-rotated")
        assert "loop-old" in out
        assert "Total: 4" in out

    def test_notifications_json_output(self, store, store_dir, notifications_file):
        """--json returns valid JSON array."""
        out, _, _ = run_cli(store_dir, "notifications", "--json")
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 3
        # Sorted by timestamp descending (most recent first)
        assert data[0]["timestamp"] == "2026-02-05T12:00:00+00:00"
        assert data[0]["event"] == "retry"

    def test_notifications_combined_filters(self, store, store_dir, notifications_file):
        """Multiple filters work together."""
        out, _, _ = run_cli(
            store_dir,
            "notifications",
            "--loop-id", "loop-001",
            "--since", "2026-02-05T11:00:00",
        )
        # Only loop-001 entry at 12:00 matches
        assert "loop-001" in out
        assert "retry" in out
        assert "Total: 1" in out

    def test_notifications_malformed_line(self, store, store_dir):
        """Malformed JSON line is skipped gracefully."""
        from pathlib import Path

        notif_path = Path(store_dir) / "notifications.jsonl"
        with open(notif_path, "w") as f:
            f.write("not valid json\n")
            f.write(json.dumps({
                "timestamp": "2026-02-05T10:00:00+00:00",
                "loop_id": "loop-good",
                "event": "completed",
                "task": "Good entry",
                "status": "completed",
                "attempts": 1,
            }) + "\n")
            f.write("{incomplete: json\n")

        out, _, _ = run_cli(store_dir, "notifications")
        assert "loop-good" in out
        assert "Total: 1" in out
