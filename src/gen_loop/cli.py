"""gen-loop-cli — CLI tool for inspecting and managing gen-loop store."""

import argparse
import json
import os
import sys
from pathlib import Path

from gen_loop import __version__
from gen_loop.store import LoopStore


STORE_DIR = os.environ.get(
    "GEN_LOOP_STORE_DIR",
    str(Path.home() / ".gen-loop" / "loop-store"),
)


def _get_store(args=None) -> LoopStore:
    store_dir = getattr(args, "store_dir", None) or STORE_DIR
    return LoopStore(store_dir)


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def cmd_list(args):
    store = _get_store(args)
    entries = store.list_all(status=args.status)
    if not entries:
        print("No loops found.")
        return

    if args.json:
        print(json.dumps(entries, indent=2))
        return

    # Table output
    print(f"{'ID':<12} {'STATUS':<12} {'ATTEMPT':<9} {'TASK'}")
    print("-" * 60)
    for e in entries:
        print(
            f"{e['id']:<12} {e['status']:<12} "
            f"{e['state']['attempt']:<9} {_truncate(e['task'], 40)}"
        )
    print(f"\nTotal: {len(entries)} loop(s)")


def cmd_show(args):
    store = _get_store(args)
    entry = store.get(args.loop_id)
    if entry is None:
        print(f"Error: loop '{args.loop_id}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(entry, indent=2))
        return

    print(f"ID:       {entry['id']}")
    print(f"Status:   {entry['status']}")
    print(f"Task:     {entry['task']}")
    print(f"Created:  {entry['created']}")
    print(f"Updated:  {entry['updated']}")
    print(f"Check:    {entry['check']['type']} — {entry['check']['command']}")
    print(f"Criteria: {entry['check']['successCriteria'] or '(any non-error)'}")
    print(f"Attempt:  {entry['state']['attempt']}/{entry['schedule']['maxRetries']}")
    print(f"Next:     {entry['state'].get('nextCheckAt', 'N/A')}")
    print(f"Expires:  {entry['schedule']['expiresAt']}")
    print(f"Notify:   {entry['notification']['method']}")

    history = entry["state"].get("history", [])
    if history:
        print(f"\nHistory ({len(history)} entries):")
        for h in history:
            output_preview = _truncate(h.get("output", ""), 50)
            print(f"  #{h['attempt']} [{h['result']}] {h['at']} — {output_preview}")


def cmd_dashboard(args):
    store = _get_store(args)
    all_entries = store.list_all()
    active = [e for e in all_entries if e["status"] == "active"]
    recent_done = sorted(
        [e for e in all_entries if e["status"] != "active"],
        key=lambda e: e.get("updated", ""),
        reverse=True,
    )[:5]

    if not active and not recent_done:
        print("No loops. All quiet.")
        return

    if active:
        print(f"Active ({len(active)}):")
        for e in active:
            print(
                f"  {e['id']}  {e['task']}  "
                f"(attempt {e['state']['attempt']}/{e['schedule']['maxRetries']}, "
                f"next: {e['state'].get('nextCheckAt', 'unknown')})"
            )
        print()

    if recent_done:
        status_marker = {
            "completed": "+", "failed": "X", "expired": "!", "cancelled": "-",
        }
        print("Recent:")
        for e in recent_done:
            marker = status_marker.get(e["status"], "?")
            print(
                f"  [{marker}] {e['id']}  {e['task']}  "
                f"({e['status']}, {e['state']['attempt']} attempts)"
            )
        print()

    by_status = {}
    for e in all_entries:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    summary = ", ".join(f"{v} {k}" for k, v in sorted(by_status.items()))
    print(f"Total: {len(all_entries)} — {summary}")


def cmd_history(args):
    store = _get_store(args)
    entries = store.list_all(status=args.status)

    all_history = []
    for e in entries:
        for h in e["state"].get("history", []):
            item = {
                "loop_id": e["id"],
                "task": e["task"],
                "status": e["status"],
                **h,
            }
            if args.keyword and args.keyword.lower() not in json.dumps(item).lower():
                continue
            all_history.append(item)

    all_history.sort(key=lambda h: h.get("at", ""), reverse=True)
    if args.limit:
        all_history = all_history[: args.limit]

    if not all_history:
        print("No history entries found.")
        return

    print(f"{'LOOP':<12} {'#':<4} {'RESULT':<12} {'TIME':<28} {'OUTPUT'}")
    print("-" * 80)
    for h in all_history:
        print(
            f"{h['loop_id']:<12} {h['attempt']:<4} {h['result']:<12} "
            f"{h['at']:<28} {_truncate(h.get('output', ''), 30)}"
        )
    print(f"\nTotal: {len(all_history)} history entries")


def cmd_cancel(args):
    store = _get_store(args)
    entry = store.get(args.loop_id)
    if entry is None:
        print(f"Error: loop '{args.loop_id}' not found.", file=sys.stderr)
        sys.exit(1)

    if entry["status"] != "active":
        print(
            f"Error: loop '{args.loop_id}' is '{entry['status']}', not active.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.yes:
        confirm = input(f"Cancel loop {args.loop_id} ({entry['task']})? [y/N] ")
        if confirm.lower() not in ("y", "yes"):
            print("Cancelled.")
            return

    store.set_status(args.loop_id, "cancelled")
    store.add_history(args.loop_id, result="cancelled", note="Cancelled via CLI")
    print(f"Loop {args.loop_id} cancelled.")


def cmd_batch(args):
    store = _get_store(args)

    if args.action == "cancel_expired":
        expired = store.list_all(status="expired")
        for e in expired:
            store.set_status(e["id"], "cancelled")
            store.add_history(e["id"], result="cancelled", note="Batch cancel_expired")
        print(f"Cancelled {len(expired)} expired loop(s).")

    elif args.action == "retry_failed":
        failed = store.list_all(status="failed")
        for e in failed:
            store.set_status(e["id"], "active")
            store.add_history(e["id"], result="retrying", note="Batch retry_failed")
        print(f"Retried {len(failed)} failed loop(s).")

    elif args.action == "cleanup_done":
        done = store.list_all(status="completed")
        for e in done:
            store.delete(e["id"])
        print(f"Cleaned up {len(done)} completed loop(s).")

    elif args.action == "summary":
        all_entries = store.list_all()
        by_status = {}
        for e in all_entries:
            by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        print(f"Total: {len(all_entries)}")
        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")

    else:
        print(f"Error: unknown action '{args.action}'.", file=sys.stderr)
        sys.exit(1)


def cmd_stats(args):
    store = _get_store(args)
    all_entries = store.list_all()

    by_status = {}
    total_attempts = 0
    completed_count = 0
    for e in all_entries:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        total_attempts += e["state"]["attempt"]
        if e["status"] == "completed":
            completed_count += 1

    total = len(all_entries)
    avg_attempts = round(total_attempts / total, 2) if total > 0 else 0
    success_rate = round(completed_count / total * 100, 1) if total > 0 else 0

    stats = {
        "total": total,
        "by_status": by_status,
        "avg_attempts": avg_attempts,
        "success_rate_pct": success_rate,
    }

    if args.json:
        print(json.dumps(stats, indent=2))
        return

    print(f"Total loops:  {total}")
    print(f"Success rate: {success_rate}%")
    print(f"Avg attempts: {avg_attempts}")
    print("By status:")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")


def cmd_notifications(args):
    """Query notification history from JSONL files."""
    store_dir = Path(getattr(args, "store_dir", None) or STORE_DIR)

    # Collect notification files to read
    files_to_read = []
    main_file = store_dir / "notifications.jsonl"
    rotated_file = store_dir / "notifications.jsonl.1"

    # Read rotated first (older), then main (newer) for chronological order
    if args.include_rotated and rotated_file.exists():
        files_to_read.append(rotated_file)
    if main_file.exists():
        files_to_read.append(main_file)

    if not files_to_read:
        print("No notifications file found.")
        return

    # Parse all notifications
    notifications = []
    for filepath in files_to_read:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    notifications.append(entry)
                except json.JSONDecodeError:
                    continue  # Skip malformed lines

    # Apply filters
    if args.loop_id:
        notifications = [n for n in notifications if n.get("loop_id") == args.loop_id]

    if args.event:
        notifications = [n for n in notifications if n.get("event") == args.event]

    if args.since:
        notifications = [n for n in notifications if n.get("timestamp", "") >= args.since]

    if args.until:
        notifications = [n for n in notifications if n.get("timestamp", "") <= args.until]

    # Sort by timestamp descending (most recent first)
    notifications.sort(key=lambda n: n.get("timestamp", ""), reverse=True)

    # Apply limit
    if args.limit:
        notifications = notifications[: args.limit]

    if not notifications:
        print("No notifications found matching filters.")
        return

    # Output
    if args.json:
        print(json.dumps(notifications, indent=2))
        return

    # Table output - columns: TIME, LOOP, EVENT, STATUS, TASK
    print(f"{'TIME':<24} {'LOOP':<12} {'EVENT':<12} {'STATUS':<12} {'TASK'}")
    print("-" * 90)
    for n in notifications:
        timestamp = n.get("timestamp", "")[:19]  # Truncate to seconds
        loop_id = n.get("loop_id", "")
        event = n.get("event", "")
        status = n.get("status", "")
        task = _truncate(n.get("task", ""), 30)
        print(f"{timestamp:<24} {loop_id:<12} {event:<12} {status:<12} {task}")

    print(f"\nTotal: {len(notifications)} notification(s)")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="gen-loop-cli",
        description="Inspect and manage gen-loop store",
    )
    parser.add_argument(
        "--version", action="version", version=f"gen-loop-cli {__version__}"
    )
    parser.add_argument(
        "--store-dir", default=None, help="Override GEN_LOOP_STORE_DIR"
    )
    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List loops")
    p_list.add_argument("--status", default=None, help="Filter by status")
    p_list.add_argument("--json", action="store_true", help="JSON output")
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = sub.add_parser("show", help="Show loop details")
    p_show.add_argument("loop_id", help="Loop ID (e.g. loop-001)")
    p_show.add_argument("--json", action="store_true", help="JSON output")
    p_show.set_defaults(func=cmd_show)

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Overview dashboard")
    p_dash.set_defaults(func=cmd_dashboard)

    # history
    p_hist = sub.add_parser("history", help="Query loop history")
    p_hist.add_argument("--status", default=None, help="Filter by loop status")
    p_hist.add_argument("--keyword", default=None, help="Filter by keyword")
    p_hist.add_argument("--limit", type=int, default=None, help="Max entries")
    p_hist.set_defaults(func=cmd_history)

    # cancel
    p_cancel = sub.add_parser("cancel", help="Cancel an active loop")
    p_cancel.add_argument("loop_id", help="Loop ID to cancel")
    p_cancel.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    p_cancel.set_defaults(func=cmd_cancel)

    # batch
    p_batch = sub.add_parser("batch", help="Batch operations")
    p_batch.add_argument(
        "action",
        choices=["cancel_expired", "retry_failed", "cleanup_done", "summary"],
        help="Batch action to run",
    )
    p_batch.set_defaults(func=cmd_batch)

    # stats
    p_stats = sub.add_parser("stats", help="Aggregate statistics")
    p_stats.add_argument("--json", action="store_true", help="JSON output")
    p_stats.set_defaults(func=cmd_stats)

    # notifications
    p_notif = sub.add_parser("notifications", help="Query notification history")
    p_notif.add_argument("--loop-id", default=None, help="Filter by loop ID")
    p_notif.add_argument(
        "--event",
        default=None,
        choices=["completed", "failed", "expired", "retry", "cancelled"],
        help="Filter by event type",
    )
    p_notif.add_argument("--since", default=None, help="Show entries after ISO timestamp")
    p_notif.add_argument("--until", default=None, help="Show entries before ISO timestamp")
    p_notif.add_argument("--limit", type=int, default=50, help="Max entries (default: 50)")
    p_notif.add_argument(
        "--include-rotated",
        action="store_true",
        help="Include rotated .jsonl.1 file",
    )
    p_notif.add_argument("--json", action="store_true", help="JSON output")
    p_notif.set_defaults(func=cmd_notifications)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
