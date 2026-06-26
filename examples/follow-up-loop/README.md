# Follow-up loop example

This directory is a compact example of the public `vigil` concept: an AI agent creates a durable follow-up loop for work that cannot be verified immediately.

## Scenario

An agent has triggered a deployment, build, download, or long-running operation. The result will only be knowable later.

Without `vigil`, the follow-up lives in chat context and may disappear when the session ends.

With `vigil`, the follow-up becomes an explicit loop:

```text
schedule -> wait -> check -> retry/backoff -> notify -> close
```

## Files

| File | Purpose |
|------|---------|
| `loop-request.json` | Example request shape for scheduling a loop. |
| `notification-event.json` | Example notification payload after a completed check. |
| `result.md` | Example human-readable result written after the loop closes. |

## Why this example exists

`vigil` is easiest to understand as a memory-and-responsibility layer: the agent does not need to remember to come back later, because the loop stores the intent, timing, check, retry policy, and notification path.
