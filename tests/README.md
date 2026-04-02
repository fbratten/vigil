# tests/ — Test Suite

## Files

### `test_store.py`
- CRUD, auto-increment, deep merge, history, atomic writes, concurrent thread safety

### `test_checks.py`
- Shell (success, failure, criteria, timeout), file_exists, http (mock), grep, unknown type

### `test_scheduler.py`
- Fires due checks, retries on failure, expires overdue, recovery on startup, clean stop

### `test_notifier.py`
- File JSONL output, multiple notifications, output inclusion, stderr logging

### `test_integration.py`
- Full lifecycle (schedule → auto-complete), file-appears-mid-retry, templates, batch ops
