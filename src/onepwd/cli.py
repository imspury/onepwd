"""Command-line interface for onepwd."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from onepwd import __version__
from onepwd.client import OnePasswordClient
from onepwd.exceptions import OnePasswordError


def _parse_assignments(items: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            raise OnePasswordError(
                f"expected field=value assignment, got '{raw}'"
            )
        key, _, value = raw.partition("=")
        fields[key] = value
    return fields


def _cmd_list(client: OnePasswordClient, args: argparse.Namespace) -> Any:
    cats = args.categories.split(",") if args.categories else None
    return client.list_items(vault=args.vault, categories=cats)


def _cmd_list_vaults(client: OnePasswordClient, args: argparse.Namespace) -> Any:
    return client.list_vaults()


def _cmd_get(client: OnePasswordClient, args: argparse.Namespace) -> Any:
    return client.get_item(args.item, vault=args.vault)


def _cmd_get_field(client: OnePasswordClient, args: argparse.Namespace) -> Any:
    return client.get_field(args.item, args.field, vault=args.vault)


def _cmd_get_fields(client: OnePasswordClient, args: argparse.Namespace) -> Any:
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    return client.get_multiple_fields(args.item, fields, vault=args.vault)


def _cmd_create(client: OnePasswordClient, args: argparse.Namespace) -> Any:
    fields = _parse_assignments(args.assignments) if args.assignments else None
    tags = args.tags.split(",") if args.tags else None
    return client.create_item(
        args.category, args.title, fields=fields, vault=args.vault, tags=tags
    )


def _cmd_update(client: OnePasswordClient, args: argparse.Namespace) -> Any:
    fields = _parse_assignments(args.assignments)
    return client.update_item(args.item, fields, vault=args.vault)


def _cmd_delete(client: OnePasswordClient, args: argparse.Namespace) -> Any:
    client.delete_item(args.item, vault=args.vault, archive=args.archive)
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onepwd",
        description="Pythonic wrapper around the 1Password CLI.",
    )
    parser.add_argument(
        "--version", action="version", version=f"onepwd {__version__}"
    )
    parser.add_argument(
        "--no-signin",
        action="store_true",
        help="Do not auto-run `op signin` if not authenticated.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List items.")
    p_list.add_argument("--vault")
    p_list.add_argument("--categories", help="Comma-separated category names.")
    p_list.set_defaults(func=_cmd_list)

    p_lv = sub.add_parser("list-vaults", help="List accessible vaults.")
    p_lv.set_defaults(func=_cmd_list_vaults)

    p_get = sub.add_parser("get", help="Get full item JSON.")
    p_get.add_argument("item")
    p_get.add_argument("--vault")
    p_get.set_defaults(func=_cmd_get)

    p_gf = sub.add_parser("get-field", help="Get a single field value.")
    p_gf.add_argument("item")
    p_gf.add_argument("field")
    p_gf.add_argument("--vault")
    p_gf.set_defaults(func=_cmd_get_field)

    p_gfs = sub.add_parser("get-fields", help="Get multiple field values.")
    p_gfs.add_argument("item")
    p_gfs.add_argument("fields", help="Comma-separated field names.")
    p_gfs.add_argument("--vault")
    p_gfs.set_defaults(func=_cmd_get_fields)

    p_create = sub.add_parser("create", help="Create a new item.")
    p_create.add_argument("category")
    p_create.add_argument("title")
    p_create.add_argument(
        "assignments", nargs="*", help="field=value assignments."
    )
    p_create.add_argument("--vault")
    p_create.add_argument("--tags", help="Comma-separated tags.")
    p_create.set_defaults(func=_cmd_create)

    p_update = sub.add_parser("update", help="Update fields on an existing item.")
    p_update.add_argument("item")
    p_update.add_argument(
        "assignments", nargs="+", help="field=value assignments."
    )
    p_update.add_argument("--vault")
    p_update.set_defaults(func=_cmd_update)

    p_del = sub.add_parser("delete", help="Delete (or archive) an item.")
    p_del.add_argument("item")
    p_del.add_argument("--vault")
    p_del.add_argument("--archive", action="store_true")
    p_del.set_defaults(func=_cmd_delete)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        client = OnePasswordClient(auto_signin=not args.no_signin)
        result = args.func(client, args)
    except OnePasswordError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if result is None:
        return 0
    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
