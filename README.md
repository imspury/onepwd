# onepwd

A Python wrapper around the [1Password CLI](https://1password.com/downloads/command-line/) (`op`). Use it from scripts to read and write items in your 1Password vaults without re-implementing subprocess plumbing every time.

## Prerequisites

1. Install the [1Password CLI](https://www.1password.dev/cli/get-started/)
2. Enable the desktop app integration (1Password app → Settings → Developer → "Integrate with 1Password CLI").
3. Sign in once interactively:
   ```bash
   op signin
   ```

## Install

```bash
pip install onepwd
```

`onepwd` ships type information (`py.typed`), so `mypy` / `pyright` will pick up its annotations.

## Quickstart

```python
from onepwd import OnePasswordClient

with OnePasswordClient() as op:
    password = op.get_field("GitHub", "password")
    fields = op.get_multiple_fields("Database Config", ["username", "password", "hostname"])
```

By default, the client raises if you're not signed in. Pass `auto_signin=True` to have it run `op signin` for you.

Concealed fields (passwords, tokens, etc.) are read with `--reveal` automatically — `get_field` returns the actual value, not `[concealed]`.

## API

| Method | Description |
|---|---|
| `list_items(vault=None, categories=None)` | List items, optionally filtered by vault and/or categories. |
| `list_vaults()` | List vaults the user can access. |
| `get_item(item_name, vault=None)` | Full item JSON. |
| `get_field(item_name, field_name, vault=None)` | Single field value as a string (concealed values are revealed). |
| `get_multiple_fields(item_name, field_names, vault=None)` | Dict of field name → value, in a single `op` call. Falls back to per-field reads if any name is unknown, so partial results still come through (missing fields → `None`). |
| `create_item(category, title, fields=None, vault=None, tags=None)` | Create a new item. |
| `update_item(item_name, fields, vault=None)` | Edit fields on an existing item. |
| `delete_item(item_name, vault=None, archive=False)` | Delete (or archive) an item. |

`OnePasswordError` is raised for any CLI failure (missing binary, not signed in, non-zero exit, malformed JSON). Error messages mask `key=value` field assignments so secrets don't leak into logs.

### `create_item` field handling

Field values are sent to `op` as a JSON template on stdin, so they never appear on the process command line (no `ps` exposure). For Login items, the labels `username`, `password`, and `notes` populate the category's built-in slots; everything else becomes a custom field. Custom field labels matching common credential keywords (`password`, `secret`, `token`, `api_key`, `credential`, `passphrase`, …) are marked `CONCEALED`; anything else is `STRING`.

## CLI

The package installs an `onepwd` console script.

| Command | Wraps |
|---|---|
| `onepwd list [--vault V] [--categories A,B]` | `list_items` |
| `onepwd list-vaults` | `list_vaults` |
| `onepwd get <item> [--vault V]` | `get_item` |
| `onepwd get-field <item> <field> [--vault V]` | `get_field` |
| `onepwd get-fields <item> <f1,f2> [--vault V]` | `get_multiple_fields` |
| `onepwd create <category> <title> [--vault V] [field=value ...]` | `create_item` |
| `onepwd update <item> [--vault V] [field=value ...]` | `update_item` |
| `onepwd delete <item> [--vault V] [--archive]` | `delete_item` |

Global flags: `--version`, `--no-signin` (skip the auto-`op signin` fallback when not authenticated).

```bash
onepwd list-vaults
onepwd get-field GitHub password
onepwd create login MyApp username=alice password=hunter2 --vault Personal
```

`get-field` prints the raw value (good for shell substitution); other commands print indented JSON.

## Examples

[`examples/smoke_test.py`](examples/smoke_test.py) exercises every public method against a real 1Password vault — useful for verifying the CLI integration end-to-end:

```bash
python examples/smoke_test.py --vault "Private"
```

## Limitations

- `update_item` passes field values as command-line assignment statements (`op item edit` has no stdin template path), so values may be visible to other processes via `ps` while `op` is running. Avoid for highly sensitive values on shared hosts.
- Synchronous only — no async API.
- Relies on a signed-in `op` session; no built-in support for service-account tokens (yet).

## License

MIT — see [LICENSE](LICENSE).
