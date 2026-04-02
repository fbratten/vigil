"""Pre-defined loop templates for common async tasks."""

from typing import Any

TEMPLATES: dict[str, dict[str, Any]] = {
    "install_check": {
        "task": "Verify package '{target}' is installed",
        "check_type": "shell",
        "check_command": "dpkg -l | grep {target}",
        "success_criteria": "ii",
        "retry_backoff_minutes": "2,5,15",
    },
    "build_check": {
        "task": "Verify build completed in '{target}'",
        "check_type": "file_exists",
        "check_command": "{target}",
        "success_criteria": "",
        "retry_backoff_minutes": "5,15,30",
    },
    "deploy_check": {
        "task": "Verify service responding at '{target}'",
        "check_type": "http",
        "check_command": "{target}",
        "success_criteria": "",
        "retry_backoff_minutes": "2,5,15",
    },
    "download_check": {
        "task": "Verify file downloaded to '{target}'",
        "check_type": "file_exists",
        "check_command": "{target}",
        "success_criteria": "",
        "retry_backoff_minutes": "1,5,15",
    },
    "docker_health": {
        "task": "Verify Docker container '{target}' is healthy",
        "check_type": "shell",
        "check_command": "docker inspect --format='{{{{.State.Health.Status}}}}' {target}",
        "success_criteria": "healthy",
        "retry_backoff_minutes": "5,15,30",
    },
    "database_ready": {
        "task": "Verify database '{target}' is accepting connections",
        "check_type": "shell",
        "check_command": "pg_isready -h {target}",
        "success_criteria": "accepting connections",
        "retry_backoff_minutes": "5,10,30",
    },
    "process_running": {
        "task": "Verify process '{target}' is running",
        "check_type": "shell",
        "check_command": "pgrep -f {target}",
        "success_criteria": "",
        "retry_backoff_minutes": "2,5,15",
    },
    "port_listening": {
        "task": "Verify port '{target}' is listening",
        "check_type": "shell",
        "check_command": "ss -tlnp | grep :{target}",
        "success_criteria": "LISTEN",
        "retry_backoff_minutes": "2,5,15",
    },
    "systemd_service": {
        "task": "Verify systemd service '{target}' is active",
        "check_type": "shell",
        "check_command": "systemctl is-active {target}",
        "success_criteria": "active",
        "retry_backoff_minutes": "5,15,30",
    },
    "dns_resolve": {
        "task": "Verify DNS resolution for '{target}'",
        "check_type": "shell",
        "check_command": "dig +short {target}",
        "success_criteria": "",
        "retry_backoff_minutes": "2,5,15",
    },
}


def apply_template(template_name: str, target: str) -> dict[str, Any]:
    """Apply a template with the given target, returning loop_schedule kwargs."""
    tmpl = TEMPLATES[template_name].copy()
    result = {}
    for key, value in tmpl.items():
        if isinstance(value, str):
            result[key] = value.format(target=target)
        else:
            result[key] = value
    return result
