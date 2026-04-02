---
title: System Overview
section: 03-architecture
order: 1
generated: 2026-04-02T16:08:44.024653
---
# System Overview

This section describes the system architecture.


## Architecture

- Pure Python, single dependency (mcp>=1.0.0)
- Internal scheduler thread manages follow-up timing
- Check types: shell command, HTTP GET, file existence, process PID
- Retry with configurable backoff
- Task expiry after configurable hours
- 13 notification methods: file, webhook, Slack, Telegram, Discord, Teams, ntfy, Pushover, Gotify, Matrix, Twilio, Google Chat, email





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

---

## See Also

- [Getting Started](../01-user-guide/01-getting-started.md)
- [Installation](../01-user-guide/02-installation.md)
- [Quick Start](../01-user-guide/03-quick-start.md)
- [Worked Examples](../01-user-guide/04-worked-examples.md)
- [Overview](../02-api-reference/01-overview.md)

---

Next: [Data Models](02-data-models.md)