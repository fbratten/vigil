# src/gen_loop/ — Source Code

## Files

### `__init__.py`
- Package init, exports `__version__` (currently 0.14.0)

### `server.py` (~490 LOC)
- MCP server entry point (`FastMCP` instance)
- **Tools (9):** `loop_schedule`, `loop_check`, `loop_list`, `loop_cancel`, `loop_history`, `loop_schedule_template`, `loop_dashboard`, `loop_batch`, `loop_write_result`
- **Function:** `main()` — starts scheduler thread, registers signal handlers (SIGTERM/SIGINT), runs MCP server
- Configurable via 32 env vars: `GEN_LOOP_STORE_DIR`, `GEN_LOOP_POLL_INTERVAL`, `GEN_LOOP_NOTIFY`, `GEN_LOOP_MAX_CONCURRENT`, plus per-channel notification config

### `store.py` (~267 LOC)
- **Class:** `LoopStore` — thread-safe file-based JSON persistence
  - Dual-lock: `threading.Lock` (cross-thread) + `fcntl.flock` (cross-process)
  - `create()`, `get()`, `update()`, `delete()`, `list_all()`
  - `add_history()`, `set_status()`, `set_next_check()`
  - `_write_atomic()` — write-to-temp + rename for crash safety
  - `_deep_merge()` — recursive dict merge for updates

### `scheduler.py` (~195 LOC)
- **Class:** `SchedulerThread(threading.Thread)` — daemon thread
  - `run()` — poll loop (configurable interval, default 10s)
  - `stop()` — signal to exit
  - `_recover()` — on startup, fire overdue loops and expire old ones
  - `_poll_and_fire()` — find due loops, spawn check sub-threads
  - `_run_check_guarded()` — semaphore-guarded check execution (max 5 concurrent)
  - `_run_check()` — execute check, handle success/failure/retry/expire

### `checks.py` (~86 LOC)
- **Dataclass:** `CheckResult` — success, output, error
- **Function:** `run_check(type, command, criteria)` — dispatcher
- **Runners (4):** `_check_shell` (30s timeout), `_check_file_exists`, `_check_http` (15s timeout, 16KB read limit), `_check_grep` (10s timeout, `pattern::filepath` format)

### `notifier.py` (~901 LOC)
- **Class:** `Notifier` — routes events to 14 delivery methods
  - `notify(entry, event_type, result)` — main dispatch
  - `_notify_file()` — append JSONL with 1MB rotation
  - `_notify_webhook()` — POST JSON with retry (3 attempts, 0/1/2s backoff, file fallback)
  - `_notify_slack()` — Block Kit formatting, reuses `_notify_webhook()`
  - `_notify_telegram()` — Bot API HTML, reuses `_notify_webhook()`
  - `_notify_discord()` — Rich embeds, reuses `_notify_webhook()`
  - `_notify_teams()` — Adaptive Cards, reuses `_notify_webhook()`
  - `_notify_ntfy()` — JSON POST with priority mapping, reuses `_notify_webhook()`
  - `_notify_pushover()` — JSON POST to api.pushover.net, reuses `_notify_webhook()`
  - `_notify_gotify()` — JSON POST with URL token auth, reuses `_notify_webhook()`
  - `_notify_matrix()` — PUT with Bearer auth, own retry logic (3 attempts)
  - `_notify_twilio_sms()` — Form-encoded POST with Basic auth, own retry logic
  - `_notify_google_chat()` — Cards v2, reuses `_notify_webhook()`
  - `_notify_email()` — SMTP with STARTTLS, own retry logic (3 attempts)
  - `_notify_stderr()` — structured log line

### `cli.py` (~325 LOC)
- **CLI tool** (`gen-loop-cli`) — 7 subcommands, reads store directly (no server dependency)
  - `list` — list loops (--status, --json)
  - `show` — show loop details (--json)
  - `dashboard` — overview of active + recent
  - `history` — query history (--status, --keyword, --limit)
  - `cancel` — cancel active loop (--yes)
  - `batch` — batch ops (cancel_expired, retry_failed, cleanup_done, summary)
  - `stats` — aggregate statistics (--json)

### `templates.py` (~89 LOC)
- **Dict:** `TEMPLATES` — 10 templates:
  - `install_check` (dpkg -l | grep), `build_check` (file_exists), `deploy_check` (http GET), `download_check` (file_exists)
  - `docker_health` (docker inspect), `database_ready` (pg_isready), `process_running` (pgrep -f), `port_listening` (ss -tlnp)
  - `systemd_service` (systemctl is-active), `dns_resolve` (dig +short)
- **Function:** `apply_template(name, target)` — substitute `{target}`, return kwargs
