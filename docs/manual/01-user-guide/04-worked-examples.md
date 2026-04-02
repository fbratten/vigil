---
title: Worked Examples
section: 01-user-guide
order: 4
generated: 2026-04-02T16:08:43.964735
---
# Worked Examples

Practical examples demonstrating common usage patterns.


## From README

### Example 1

```
gen-loop-cli list                      # List all loops
gen-loop-cli list --status active      # Filter by status
gen-loop-cli list --json               # JSON output
gen-loop-cli show loop-001             # Show loop details
gen-loop-cli dashboard                 # Overview of active + recent
gen-loop-cli history --limit 10        # Recent history entries
gen-loop-cli stats --json              # Aggregate statistics
gen-loop-cli cancel loop-001 --yes     # Cancel a loop
gen-loop-cli batch summary             # Status summary
gen-loop-cli batch cancel_expired      # Batch cancel expired loops
gen-loop-cli notifications             # Query notification history
gen-loop-cli notifications --loop-id loop-001 --event completed --limit 20
gen-loop-cli notifications --include-rotated --json
```

### Example 2

```
# Install
cd gen-loop-mcp && uv pip install -e ".[dev]"

# Run tests (148 tests)
pytest tests/ -v

# Use via mcporter
mcporter call gen-loop.loop_schedule task="Check build" check_command="ls dist/" check_after_minutes=2
mcporter call gen-loop.loop_dashboard
mcporter call gen-loop.loop_list

# Use CLI directly
gen-loop-cli list
gen-loop-cli dashboard
```

---

## See Also

- [Overview](../02-api-reference/01-overview.md)
- [System Overview](../03-architecture/01-system-overview.md)
- [Data Models](../03-architecture/02-data-models.md)
- [Configuration](../04-reference/01-configuration.md)
- [Error Handling](../04-reference/02-error-handling.md)

---

Previous: [Quick Start](03-quick-start.md)