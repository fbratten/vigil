# ARCHITECTURE.md — Gen-Loop MCP Server

## Overview
Gen-Loop is a **standalone** stdio MCP server that manages its own scheduling. Unlike loop-mcp (which depends on OpenClaw cron), gen-loop runs an internal scheduler thread that polls the store and fires checks autonomously.

## Design Principles
1. **Zero external dependencies** — only the `mcp` SDK + Python stdlib
2. **Self-contained scheduling** — internal daemon thread, no external cron
3. **Thread-safe store** — fcntl file locking prevents corruption
4. **Recovery on restart** — reads store on startup, resumes pending loops
5. **Pluggable notifications** — file, webhook, stderr (not tied to any platform)
6. **Same data model** — compatible store format with loop-mcp

## Data Flow
```
Agent calls loop_schedule(task, check, timing)
  → Store creates loop-{id}.json with nextCheckAt set
  → Scheduler thread polls every 10s
  → When nextCheckAt <= now:
      → Run check (in sub-thread with timeout)
      → Success → close loop, notify
      → Failure → recalculate nextCheckAt with backoff, notify
      → Max retries → mark failed, notify
      → Past expiresAt → mark expired, notify
```

## Scheduler Thread Design
```python
class SchedulerThread(threading.Thread):
    daemon = True  # Dies with main process

    def run(self):
        while not self._stop_event.is_set():
            self._poll_and_fire()
            self._stop_event.wait(self.poll_interval)

    def _poll_and_fire(self):
        for loop in store.list_all(status="active"):
            if loop.nextCheckAt <= now:
                # Run in sub-thread to avoid blocking
                threading.Thread(target=self._run_check, args=(loop,)).start()
```

## Thread Safety
- **Store writes:** `fcntl.flock(LOCK_EX)` on a lockfile per store directory
- **Single writer pattern:** All writes go through `LoopStore._write()` which acquires the lock
- **Reads don't lock:** JSON files are written atomically (write to temp, rename)

## Notification System
Three notification methods, configurable per-loop or via env var:
- **File:** Append JSONL to `notifications.jsonl` — external tools can `tail -f`
- **Webhook:** POST JSON to a URL (fire-and-forget, 5s timeout)
- **Stderr:** Structured log lines visible to MCP client

## Recovery
On startup, the scheduler thread:
1. Reads all `active` loops from store
2. For any where `nextCheckAt` is in the past, fires the check immediately
3. For any where `expiresAt` is in the past, marks as expired
4. Normal polling resumes

## Data Model
Same as loop-mcp with added `notification` field. See `PLAN.md` for full schema.
