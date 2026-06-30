#!/usr/bin/env python3
"""End-to-end smoke test for onepwd against a real 1Password vault.

This exercises every public method of :class:`OnePasswordClient`. It is
deliberately self-contained and *non-destructive to your existing data*: it
only ever touches a single item that it creates itself, identified by a unique
title, and it always deletes that item before exiting — even on failure.

It will:
  1. confirm the CLI is reachable and you're signed in
  2. list vaults and items (read-only)
  3. create a throwaway Login item (with a username + password)
  4. read it back via get_item / get_field / get_multiple_fields
  5. update a field on it
  6. delete it

Usage:
    python examples/smoke_test.py --vault "Private"

Requires a signed-in `op` session and write access to the named vault.
Nothing else in the vault is modified.
"""

from __future__ import annotations

import argparse
import sys

from onepwd import OnePasswordClient, OnePasswordError

# A title unlikely to collide with anything real. The smoke test creates this
# item, operates on it, and deletes it — it never edits items it didn't create.
ITEM_TITLE = "onepwd-smoke-test-DELETE-ME"


def _section(label: str) -> None:
    print(f"\n=== {label} ===")


def run(vault: str) -> None:
    with OnePasswordClient() as op:
        _section("Listing vaults")
        vaults = op.list_vaults()
        print(f"{len(vaults)} vault(s) accessible: {[v.get('name') for v in vaults]}")

        _section(f"Listing items in vault {vault!r}")
        items = op.list_items(vault=vault)
        print(f"{len(items)} existing item(s) (left untouched)")

        _section(f"Creating throwaway item {ITEM_TITLE!r}")
        created = op.create_item(
            "login",
            ITEM_TITLE,
            fields={"username": "smoke-user", "password": "initial-secret"},
            vault=vault,
            tags=["onepwd-smoke-test"],
        )
        item_id = created["id"]
        print(f"created item id={item_id}")

        try:
            _section("Reading it back with get_item")
            fetched = op.get_item(item_id, vault=vault)
            print(f"title={fetched.get('title')!r} category={fetched.get('category')!r}")

            _section("get_field(password)")
            password = op.get_field(item_id, "password", vault=vault)
            assert password == "initial-secret", f"unexpected password: {password!r}"
            print("password matches what we set")

            _section("get_multiple_fields(username, password)")
            fields = op.get_multiple_fields(
                item_id, ["username", "password"], vault=vault
            )
            assert fields["username"] == "smoke-user", fields
            assert fields["password"] == "initial-secret", fields
            print(f"got: {fields}")

            _section("Updating the password")
            op.update_item(item_id, {"password": "rotated-secret"}, vault=vault)
            rotated = op.get_field(item_id, "password", vault=vault)
            assert rotated == "rotated-secret", f"update did not take: {rotated!r}"
            print("password successfully rotated")
        finally:
            _section("Cleaning up (deleting the throwaway item)")
            op.delete_item(item_id, vault=vault)
            print("deleted")

    print("\nSmoke test passed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault",
        required=True,
        help="Vault to create the throwaway test item in (you need write access).",
    )
    args = parser.parse_args(argv)

    try:
        run(args.vault)
    except OnePasswordError as e:
        print(f"\nSmoke test FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
