"""Tools module — file read/write and command execution with safety boundaries."""

import os
import subprocess
from mecha.models import ActionResult


def _is_safe_path(path: str, project_root: str) -> bool:
    """Check that a path stays within the project root (no traversal)."""
    real_project = os.path.realpath(project_root)
    # Resolve relative to project root
    full_path = os.path.realpath(os.path.join(project_root, path))
    # Must start with project root
    return full_path.startswith(real_project + os.sep) or full_path == real_project


def read_file(path: str, project_root: str) -> ActionResult:
    """Read a file within the project root.

    Args:
        path: Relative path to the file.
        project_root: Absolute path to the project root.

    Returns:
        ActionResult with file content on success, error on failure.
    """
    if not _is_safe_path(path, project_root):
        return ActionResult(
            success=False,
            error=f"Security: path traversal detected for '{path}'"
        )

    full_path = os.path.join(project_root, path)

    if not os.path.exists(full_path):
        return ActionResult(
            success=False,
            error=f"File not found: {path}"
        )

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        return ActionResult(success=True, output=content)
    except Exception as e:
        return ActionResult(success=False, error=str(e))


def write_file(path: str, content: str, project_root: str, max_size: int = 1_048_576) -> ActionResult:
    """Write content to a file within the project root.

    Args:
        path: Relative path to the file.
        content: Content to write.
        project_root: Absolute path to the project root.
        max_size: Maximum allowed file size in bytes (default 1MB).

    Returns:
        ActionResult indicating success or failure.
    """
    if not _is_safe_path(path, project_root):
        return ActionResult(
            success=False,
            error=f"Security: path traversal detected for '{path}'"
        )

    if len(content.encode("utf-8")) > max_size:
        return ActionResult(
            success=False,
            error=f"File size exceeds limit of {max_size} bytes"
        )

    full_path = os.path.join(project_root, path)

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return ActionResult(success=True, output=f"Written {len(content)} bytes to {path}")
    except Exception as e:
        return ActionResult(success=False, error=str(e))


def run_command(command: str, project_root: str, timeout: int = 30) -> ActionResult:
    """Execute a shell command within the project root.

    Args:
        command: Shell command to execute.
        project_root: Working directory for the command.
        timeout: Command timeout in seconds.

    Returns:
        ActionResult with stdout, stderr, and exit code.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return ActionResult(
            success=result.returncode == 0,
            output=result.stdout.strip(),
            error=result.stderr.strip(),
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return ActionResult(
            success=False,
            error=f"Command timed out after {timeout}s: {command}",
            exit_code=-1,
        )
    except Exception as e:
        return ActionResult(success=False, error=str(e), exit_code=-1)