"""Tests for the thread-safe store."""

import json
import threading
import pytest
from gen_loop.store import LoopStore


@pytest.fixture
def store(tmp_path):
    return LoopStore(tmp_path / "loop-store")


class TestCRUD:
    def test_create_defaults(self, store):
        e = store.create(task="Test task")
        assert e["id"] == "loop-001"
        assert e["status"] == "active"
        assert e["check"]["type"] == "shell"
        assert e["notification"]["method"] == "file"

    def test_auto_increment(self, store):
        e1 = store.create(task="A")
        e2 = store.create(task="B")
        assert e1["id"] == "loop-001"
        assert e2["id"] == "loop-002"

    def test_get_existing(self, store):
        store.create(task="Find me")
        assert store.get("loop-001")["task"] == "Find me"

    def test_get_missing(self, store):
        assert store.get("loop-999") is None

    def test_update(self, store):
        store.create(task="Original")
        updated = store.update("loop-001", {"task": "Modified"})
        assert updated["task"] == "Modified"
        assert store.get("loop-001")["task"] == "Modified"

    def test_deep_merge(self, store):
        store.create(task="Deep", context={"a": 1, "b": 2})
        store.update("loop-001", {"context": {"b": 99, "c": 3}})
        assert store.get("loop-001")["context"] == {"a": 1, "b": 99, "c": 3}

    def test_delete(self, store):
        store.create(task="Gone")
        assert store.delete("loop-001") is True
        assert store.get("loop-001") is None
        assert store.delete("loop-001") is False

    def test_list_all(self, store):
        store.create(task="A")
        store.create(task="B")
        store.create(task="C")
        assert len(store.list_all()) == 3

    def test_list_filtered(self, store):
        store.create(task="Active")
        e2 = store.create(task="Done")
        store.set_status(e2["id"], "completed")
        assert len(store.list_all(status="active")) == 1
        assert len(store.list_all(status="completed")) == 1


class TestHistory:
    def test_add_history(self, store):
        store.create(task="Track me")
        e = store.add_history("loop-001", result="failure", output="nope")
        assert e["state"]["attempt"] == 1
        assert e["state"]["history"][0]["result"] == "failure"

    def test_multiple_attempts(self, store):
        store.create(task="Multi")
        store.add_history("loop-001", result="failure")
        store.add_history("loop-001", result="failure")
        e = store.add_history("loop-001", result="success")
        assert e["state"]["attempt"] == 3

    def test_truncates_output(self, store):
        store.create(task="Big")
        e = store.add_history("loop-001", result="failure", output="x" * 5000)
        assert len(e["state"]["history"][0]["output"]) == 2000


class TestAtomicWrites:
    def test_persists_to_disk(self, store):
        store.create(task="Persist")
        path = store.store_dir / "loop-001.json"
        assert path.exists()
        with open(path) as f:
            assert json.load(f)["task"] == "Persist"

    def test_concurrent_creates(self, store):
        """Multiple threads creating loops shouldn't corrupt."""
        errors = []

        def create_loop(n):
            try:
                store.create(task=f"Task {n}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_loop, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        entries = store.list_all()
        assert len(entries) == 10
