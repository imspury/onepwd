"""Client for interacting with the 1Password CLI."""

from __future__ import annotations

import json
import logging
import subprocess
from types import TracebackType
from typing import Any

from onepwd._process import _run_op
from onepwd.exceptions import OnePasswordError

logger = logging.getLogger(__name__)

_NOT_SIGNED_IN_MARKERS = (
    "not currently signed in",
    "not signed in",
    "session expired",
    "no account",
)

_CONCEALED_LABEL_HINTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "api key",
    "apikey",
    "credential",
    "private",
    "passphrase",
)

# `purpose` links a field to a category's built-in slot (vs. adding a custom
# field with the same label). Set for the three labels op recognises.
_PURPOSE_BY_LABEL = {
    "username": "USERNAME",
    "password": "PASSWORD",
    "notesplain": "NOTES",
    "notes": "NOTES",
}


class OnePasswordClient:
    """Wrapper around the 1Password CLI (`op`).

    Methods shell out to `op` and parse its JSON output. All failures surface
    as :class:`OnePasswordError`.
    """

    def __init__(self, auto_signin: bool = False) -> None:
        """Initialise the client and confirm the CLI is usable.

        Args:
            auto_signin: If True, run ``op signin`` interactively when the user
                is not already authenticated. If False, raise if not signed in.
        """
        self._check_cli_installed(auto_signin)

    def __enter__(self) -> OnePasswordClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # The `op` daemon owns session state; there is nothing to release here.
        # Don't be tempted to call `op signout` — that would log the user out
        # of their interactive session, which they did not ask for.
        return None

    def _check_cli_installed(self, auto_signin: bool) -> None:
        try:
            subprocess.run(["op", "--version"], capture_output=True, check=True)
        except FileNotFoundError as e:
            raise OnePasswordError(
                "1Password CLI not found. Install it from "
                "https://1password.com/downloads/command-line/"
            ) from e
        except subprocess.CalledProcessError as e:
            raise OnePasswordError(f"1Password CLI failed to run: {e}") from e

        result = subprocess.run(
            ["op", "whoami"], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").lower()
            if any(marker in stderr for marker in _NOT_SIGNED_IN_MARKERS):
                if auto_signin:
                    logger.info("Not signed in to 1Password CLI; attempting signin...")
                    self._perform_signin()
                    return
                raise OnePasswordError(
                    "Not signed in to 1Password CLI. Run `op signin` first, or "
                    "construct OnePasswordClient(auto_signin=True)."
                )
            raise OnePasswordError(
                f"`op whoami` failed: {(result.stderr or '').strip() or 'unknown error'}"
            )

        email = _extract_field(result.stdout, "Email:")
        user_id = _extract_field(result.stdout, "User ID:")
        logger.info("1Password CLI ready (email=%s user_id=%s)", email, user_id)

    def _perform_signin(self) -> None:
        try:
            subprocess.run(["op", "signin"], check=True)
            logger.info("Signed in to 1Password CLI")
        except subprocess.CalledProcessError as e:
            raise OnePasswordError(f"Failed to sign in to 1Password CLI: {e}") from e
        except KeyboardInterrupt as e:
            raise OnePasswordError("Signin cancelled by user") from e

    def list_items(
        self,
        vault: str | None = None,
        categories: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List items, optionally filtered by vault and/or category."""
        args = ["item", "list", "--format=json"]
        if vault:
            args.append(f"--vault={vault}")
        if categories:
            args.append(f"--categories={','.join(categories)}")
        return _run_op(args)

    def list_vaults(self) -> list[dict[str, Any]]:
        """List vaults the user can access."""
        return _run_op(["vault", "list", "--format=json"])

    def get_item(self, item_name: str, vault: str | None = None) -> dict[str, Any]:
        """Return the full JSON for an item (looked up by name, ID, or UUID)."""
        args = ["item", "get", item_name, "--format=json"]
        if vault:
            args.append(f"--vault={vault}")
        return _run_op(args)

    def get_field(
        self,
        item_name: str,
        field_name: str,
        vault: str | None = None,
    ) -> str:
        """Return a single field value as a string (whitespace-stripped).

        Concealed fields (passwords, tokens) are revealed — without ``--reveal``
        ``op`` returns ``[concealed]``, which is never what a programmatic
        caller wants.
        """
        args = [
            "item",
            "get",
            item_name,
            f"--fields={field_name}",
            "--reveal",
        ]
        if vault:
            args.append(f"--vault={vault}")
        return _run_op(args, parse_json=False).strip()

    def get_multiple_fields(
        self,
        item_name: str,
        field_names: list[str],
        vault: str | None = None,
    ) -> dict[str, str | None]:
        """Return a dict of field name → value.

        Issues a single ``op item get`` call and maps the returned field array
        back to the requested names. If ``op`` rejects the batch because *any*
        of the names is unknown, falls back to per-field reads so the caller
        still gets values for the names that do exist (missing ones come back
        as ``None``).
        """
        if not field_names:
            return {}

        args = [
            "item",
            "get",
            item_name,
            f"--fields={','.join(field_names)}",
            "--reveal",
            "--format=json",
        ]
        if vault:
            args.append(f"--vault={vault}")

        try:
            payload = _run_op(args)
        except OnePasswordError as e:
            logger.info(
                "Batched fields read failed for '%s' (%s); falling back to per-field.",
                item_name,
                e,
            )
            return self._get_fields_individually(item_name, field_names, vault)

        # Single-field requests come back as a dict; multi-field as a list.
        entries = [payload] if isinstance(payload, dict) else list(payload)
        by_label = {entry.get("label"): entry.get("value") for entry in entries}
        by_id = {entry.get("id"): entry.get("value") for entry in entries}
        return {name: by_label.get(name, by_id.get(name)) for name in field_names}

    def _get_fields_individually(
        self,
        item_name: str,
        field_names: list[str],
        vault: str | None,
    ) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for name in field_names:
            try:
                result[name] = self.get_field(item_name, name, vault=vault)
            except OnePasswordError as e:
                logger.warning("Could not retrieve field '%s': %s", name, e)
                result[name] = None
        return result

    def create_item(
        self,
        category: str,
        title: str,
        fields: dict[str, str] | None = None,
        vault: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new item.

        Field values are sent to ``op`` via stdin as a JSON template, so they
        never appear on the process command line (no ``ps`` exposure). Field
        labels containing common credential keywords (``password``, ``token``,
        ``secret``, …) are marked CONCEALED; everything else is STRING.
        """
        args = ["item", "create", "--format=json"]
        if vault:
            args.append(f"--vault={vault}")
        if tags:
            args.append(f"--tags={','.join(tags)}")

        if not fields:
            args.extend([f"--category={category}", f"--title={title}"])
            return _run_op(args)

        # When stdin carries a template, `op` rejects --category/--title on
        # argv as a conflict — title and category live in the template.
        template = {
            "title": title,
            "category": category.upper(),
            "fields": [_field_template(label, value) for label, value in fields.items()],
        }
        return _run_op(args, input=json.dumps(template))

    def update_item(
        self,
        item_name: str,
        fields: dict[str, str],
        vault: str | None = None,
    ) -> dict[str, Any]:
        """Edit fields on an existing item.

        ``op item edit`` has no stdin template, so values are passed as
        ``label=value`` argv entries — they may be visible to other processes
        via ``ps`` for the duration of the call. Avoid for highly sensitive
        values on shared hosts.
        """
        args = ["item", "edit", item_name, "--format=json"]
        if vault:
            args.append(f"--vault={vault}")
        args.extend(f"{k}={v}" for k, v in fields.items())
        return _run_op(args)

    def delete_item(
        self,
        item_name: str,
        vault: str | None = None,
        archive: bool = False,
    ) -> None:
        """Delete an item. Pass ``archive=True`` to archive instead."""
        args = ["item", "delete", item_name]
        if vault:
            args.append(f"--vault={vault}")
        if archive:
            args.append("--archive")
        _run_op(args, parse_json=False)


def _field_template(label: str, value: str) -> dict[str, Any]:
    """Build one entry of the JSON template's ``fields`` array.

    Labels recognised by `op` (``username``, ``password``, ``notes``) get a
    ``purpose`` so they map to the category's built-in slot — without it, op
    creates a *custom* field of the same name alongside the built-in one,
    leaving you with two ``password`` fields per item.
    """
    lowered = label.lower()
    field: dict[str, Any] = {"id": label, "label": label, "value": value}
    purpose = _PURPOSE_BY_LABEL.get(lowered)
    if purpose:
        field["purpose"] = purpose
        # Built-in PASSWORD/USERNAME/NOTES already carry the right type;
        # `op` errors if you pass an explicit type alongside `purpose`.
        return field
    field["type"] = (
        "CONCEALED"
        if any(hint in lowered for hint in _CONCEALED_LABEL_HINTS)
        else "STRING"
    )
    return field


def _extract_field(text: str, label: str) -> str:
    for line in text.splitlines():
        if line.startswith(label):
            return line.split(":", 1)[1].strip()
    return "unknown"
