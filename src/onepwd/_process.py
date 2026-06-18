"""Internal helper for invoking the `op` CLI."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from onepwd.exceptions import OnePasswordError


def _redact_args(args: list[str]) -> str:
    """Format args for error output, masking values of bare `key=value` assignments.

    Long flags (``--vault=Personal``, ``--fields=password``) are kept verbatim —
    they are not secrets. Positional ``label=value`` assignments are masked,
    since they may carry credentials supplied by the caller.
    """
    parts: list[str] = []
    for a in args:
        if a.startswith("--") or "=" not in a:
            parts.append(a)
        else:
            key, _, _ = a.partition("=")
            parts.append(f"{key}=***")
    return " ".join(parts)


def _run_op(
    args: list[str],
    *,
    parse_json: bool = True,
    input: str | None = None,
) -> Any:
    """Run `op <args>` and return parsed JSON (or raw stdout when parse_json=False).

    Raises OnePasswordError if the CLI is missing, exits non-zero, or emits
    output that cannot be parsed as JSON. Pass ``input`` to send data on stdin
    (used for ``--template=-`` to avoid putting secrets on the command line).
    """
    cmd = ["op", *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, input=input
        )
    except FileNotFoundError as e:
        raise OnePasswordError(
            "1Password CLI not found. Install it from "
            "https://1password.com/downloads/command-line/"
        ) from e

    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "unknown error"
        raise OnePasswordError(f"op {_redact_args(args)} failed: {stderr}")

    if not parse_json:
        return result.stdout

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise OnePasswordError(f"failed to parse op output as JSON: {e}") from e
