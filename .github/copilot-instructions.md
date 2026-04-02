## gen-loop-mcp - Copilot Instructions

gen-loop-mcp is a standalone self-scheduling follow-up MCP server. No external scheduler, no gateway, no cron.

### Key Files
- `src/gen_loop/server.py` - FastMCP server with 11 tools
- `src/gen_loop/scheduler.py` - Internal scheduler thread (10s poll interval)
- `src/gen_loop/checks.py` - Check executors (shell, HTTP, file, process)
- `src/gen_loop/notifier.py` - 13 notification channels
- `src/gen_loop/store.py` - SQLite-backed task store
- `src/gen_loop/cli.py` - CLI interface
- `tests/` - 7 test files, 148 tests

### Architecture
- Pure Python, single dependency (mcp>=1.0.0)
- Internal scheduler thread manages follow-up timing
- Check types: shell command, HTTP GET, file existence, process PID
- Retry with configurable backoff
- Task expiry after configurable hours
- 13 notification methods: file, webhook, Slack, Telegram, Discord, Teams, ntfy, Pushover, Gotify, Matrix, Twilio, Google Chat, email

### Testing
Run: `python -m pytest tests/ -v`
All 148 tests must pass before merging.
