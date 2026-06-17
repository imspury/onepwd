"""Internal helper for invoking the `op` CLI."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from onepwd.exceptions import OnePasswordError


def _run_op(args: list[str], *, parse_json: bool = True) -> Any:
    """Run `op <args>` and return parsed JSON (or raw stdout when parse_json=False).

    Raises OnePasswordError if the CLI is missing, exits non-zero, or emits
    output that cannot be parsed as JSON.
    """
    cmd = ["op", *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        raise OnePasswordError(
            "1Password CLI not found. Install it from "
            "https://1password.com/downloads/command-line/"
        ) from e

    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "unknown error"
        raise OnePasswordError(f"op {' '.join(args)} failed: {stderr}")

    if not parse_json:
        return result.stdout

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise OnePasswordError(f"failed to parse op output as JSON: {e}") from e
