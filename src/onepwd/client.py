"""Client for interacting with the 1Password CLI."""

from __future__ import annotations

import logging
import subprocess
from types import TracebackType
from typing import Any

from onepwd._process import _run_op
from onepwd.exceptions import OnePasswordError

logger = logging.getLogger(__name__)


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

        try:
            result = subprocess.run(
                ["op", "whoami"], capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError:
            if auto_signin:
                logger.info("Not signed in to 1Password CLI; attempting signin...")
                self._perform_signin()
                return
            raise OnePasswordError(
                "Not signed in to 1Password CLI. Run `op signin` first, or "
                "construct OnePasswordClient(auto_signin=True)."
            ) from None

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
        """Return a single field value as a string (whitespace-stripped)."""
        args = ["item", "get", item_name, f"--fields={field_name}"]
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

        Fields that fail to load are returned as ``None`` so callers can decide
        whether to fail or fall back.
        """
        result: dict[str, str | None] = {}
        for field_name in field_names:
            try:
                result[field_name] = self.get_field(item_name, field_name, vault)
            except OnePasswordError as e:
                logger.warning("Could not retrieve field '%s': %s", field_name, e)
                result[field_name] = None
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

        ``fields`` are passed to ``op item create`` as assignment statements
        (``label=value``). Note: values appear on the command line and may be
        visible to other processes via ``ps`` for the duration of the call.
        """
        args = [
            "item",
            "create",
            f"--category={category}",
            f"--title={title}",
            "--format=json",
        ]
        if vault:
            args.append(f"--vault={vault}")
        if tags:
            args.append(f"--tags={','.join(tags)}")
        if fields:
            args.extend(f"{k}={v}" for k, v in fields.items())
        return _run_op(args)

    def update_item(
        self,
        item_name: str,
        fields: dict[str, str],
        vault: str | None = None,
    ) -> dict[str, Any]:
        """Edit fields on an existing item.

        Same ``ps``-visibility caveat as :meth:`create_item`.
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


def _extract_field(text: str, label: str) -> str:
    for line in text.splitlines():
        if label in line:
            return line.split(":", 1)[1].strip()
    return "unknown"
