"""Check type implementations — identical to loop-mcp, zero external deps."""

import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path

from gen_loop import __version__

HTTP_READ_LIMIT = 16384  # bytes to read from HTTP responses


@dataclass
class CheckResult:
    """Result of running a loop check."""
    success: bool
    output: str
    error: str = ""


def run_check(check_type: str, command: str, success_criteria: str = "") -> CheckResult:
    """Execute a check and return the result."""
    runners = {
        "shell": _check_shell,
        "file_exists": _check_file_exists,
        "grep": _check_grep,
        "http": _check_http,
    }
    runner = runners.get(check_type)
    if runner is None:
        return CheckResult(success=False, output="", error=f"Unknown check type: {check_type}")
    try:
        return runner(command, success_criteria)
    except Exception as e:
        return CheckResult(success=False, output="", error=str(e))


def _check_shell(command: str, success_criteria: str) -> CheckResult:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        if success_criteria:
            success = success_criteria.lower() in output.lower()
        else:
            success = result.returncode == 0
        return CheckResult(success=success, output=output or result.stderr.strip())
    except subprocess.TimeoutExpired:
        return CheckResult(success=False, output="", error="Command timed out (30s)")


def _check_file_exists(path: str, success_criteria: str) -> CheckResult:
    exists = Path(path).exists()
    return CheckResult(success=exists, output=f"{'Found' if exists else 'Not found'}: {path}")


def _check_http(url: str, success_criteria: str) -> CheckResult:
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"gen-loop-mcp/{__version__}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            body = resp.read(HTTP_READ_LIMIT).decode("utf-8", errors="replace")
            if success_criteria:
                success = success_criteria.lower() in body.lower()
            else:
                success = 200 <= status < 300
            return CheckResult(success=success, output=f"HTTP {status} — {body[:500]}")
    except urllib.error.HTTPError as e:
        return CheckResult(success=False, output=f"HTTP {e.code} — {e.reason}")
    except urllib.error.URLError as e:
        return CheckResult(success=False, output="", error=f"Connection failed: {e.reason}")
    except TimeoutError:
        return CheckResult(success=False, output="", error="HTTP request timed out (15s)")


def _check_grep(command: str, success_criteria: str) -> CheckResult:
    if "::" not in command:
        return CheckResult(success=False, output="", error="Grep format: 'pattern::filepath'")
    pattern, filepath = command.split("::", 1)
    try:
        result = subprocess.run(["grep", "-i", pattern, filepath], capture_output=True, text=True, timeout=10)
        return CheckResult(success=result.returncode == 0, output=result.stdout.strip() or "No match found")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return CheckResult(success=False, output="", error=str(e))
