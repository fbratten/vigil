---
title: Quick Start
section: 01-user-guide
order: 3
generated: 2026-04-02T16:08:43.953134
---
# Quick Start

```bash
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

Previous: [Installation](02-installation.md) | Next: [Worked Examples](04-worked-examples.md)