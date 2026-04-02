"""Integration tests — full lifecycle with internal scheduler."""

import time
import pytest
from gen_loop.store import LoopStore
from gen_loop.scheduler import SchedulerThread
from gen_loop.notifier import Notifier
from gen_loop.templates import TEMPLATES, apply_template


@pytest.fixture
def env(tmp_path):
    store_dir = tmp_path / "loop-store"
    store = LoopStore(store_dir)
    notifier = Notifier(store_dir)
    events = []

    def on_event(entry, event_type, result):
        events.append((entry["id"], event_type))
        notifier.notify(entry, event_type, result)

    return store, notifier, on_event, events


class TestFullLifecycle:
    def test_schedule_auto_complete(self, env):
        """Schedule → scheduler fires → auto-completes."""
        store, notifier, on_event, events = env

        store.create(task="Auto check", check_command="echo auto",
                     success_criteria="auto", check_after_minutes=0)

        sched = SchedulerThread(store=store, poll_interval=0.5, on_event=on_event)
        sched.start()
        time.sleep(2)
        sched.stop()
        sched.join(timeout=3)

        assert store.get("loop-001")["status"] == "completed"
        assert ("loop-001", "completed") in events
        # Notification file should exist
        assert notifier.notifications_file.exists()

    def test_schedule_fail_retry_then_file_appears(self, env, tmp_path):
        """Schedule file check → fails → file created → succeeds on retry."""
        store, notifier, on_event, events = env
        target = tmp_path / "output.txt"

        store.create(task="Wait for file", check_type="file_exists",
                     check_command=str(target), check_after_minutes=0,
                     max_retries=5, retry_backoff_minutes=[0])

        sched = SchedulerThread(store=store, poll_interval=0.5, on_event=on_event)
        sched.start()
        time.sleep(1.5)

        # File appears mid-loop
        target.write_text("done!")
        time.sleep(2)

        sched.stop()
        sched.join(timeout=3)

        final = store.get("loop-001")
        assert final["status"] == "completed"
        assert final["state"]["attempt"] >= 2  # At least one retry before success


class TestTemplates:
    def test_all_exist(self):
        expected = {
            "install_check", "build_check", "deploy_check", "download_check",
            "docker_health", "database_ready", "process_running", "port_listening",
            "systemd_service", "dns_resolve",
        }
        assert set(TEMPLATES.keys()) == expected

    def test_apply_systemd_service(self):
        p = apply_template("systemd_service", "nginx")
        assert p["check_type"] == "shell"
        assert "nginx" in p["check_command"]
        assert p["success_criteria"] == "active"

    def test_apply_dns_resolve(self):
        p = apply_template("dns_resolve", "example.com")
        assert p["check_type"] == "shell"
        assert "example.com" in p["check_command"]
        assert p["success_criteria"] == ""

    def test_apply_install(self):
        p = apply_template("install_check", "libnspr4")
        assert "libnspr4" in p["task"]
        assert p["check_type"] == "shell"

    def test_apply_deploy(self):
        p = apply_template("deploy_check", "http://localhost:8080")
        assert p["check_type"] == "http"

    def test_apply_docker_health(self):
        p = apply_template("docker_health", "my-container")
        assert p["check_type"] == "shell"
        assert "my-container" in p["check_command"]
        assert p["success_criteria"] == "healthy"

    def test_apply_port_listening(self):
        p = apply_template("port_listening", "8080")
        assert p["check_type"] == "shell"
        assert ":8080" in p["check_command"]
        assert p["success_criteria"] == "LISTEN"


class TestBatchOps:
    def test_mixed_status_batch(self, env):
        store, _, _, _ = env
        store.create(task="Active")
        e2 = store.create(task="Expired")
        store.set_status(e2["id"], "expired")
        e3 = store.create(task="Failed")
        store.set_status(e3["id"], "failed")

        # Cancel expired
        for e in store.list_all(status="expired"):
            store.set_status(e["id"], "cancelled")
        assert len(store.list_all(status="expired")) == 0
        assert len(store.list_all(status="active")) == 1

        # Retry failed
        for e in store.list_all(status="failed"):
            store.set_status(e["id"], "active")
        assert len(store.list_all(status="active")) == 2
