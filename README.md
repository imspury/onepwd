# onepwd

Pythonic wrapper around the [1Password CLI](https://1password.com/downloads/command-line/) (`op`). Use it from scripts to read and write items in your 1Password vaults without re-implementing subprocess plumbing every time.

## Prerequisites

1. Install the 1Password CLI:
   ```bash
   brew install 1password-cli      # macOS
   ```
2. Enable the desktop app integration (1Password app → Settings → Developer → "Integrate with 1Password CLI").
3. Sign in once interactively:
   ```bash
   op signin
   ```

## Install

```bash
pip install onepwd
```

## Quickstart

```python
from onepwd import OnePasswordClient

with OnePasswordClient() as op:
    password = op.get_field("GitHub", "password")
    fields = op.get_multiple_fields("Database Config", ["username", "password", "hostname"])
```

Pass `auto_signin=True` to have the client run `op signin` for you when not already authenticated.

## API

| Method | Description |
|---|---|
| `list_items(vault=None, categories=None)` | List items, optionally filtered by vault and/or categories. |
| `list_vaults()` | List vaults the user can access. |
| `get_item(item_name, vault=None)` | Full item JSON. |
| `get_field(item_name, field_name, vault=None)` | Single field value as a string. |
| `get_multiple_fields(item_name, field_names, vault=None)` | Dict of field name → value. |
| `create_item(category, title, fields=None, vault=None, tags=None)` | Create a new item. |
| `update_item(item_name, fields, vault=None)` | Edit fields on an existing item. |
| `delete_item(item_name, vault=None, archive=False)` | Delete (or archive) an item. |

`OnePasswordError` is raised for any CLI failure (missing binary, not signed in, non-zero exit, malformed JSON).

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

```bash
onepwd list-vaults
onepwd get-field GitHub password
onepwd create login MyApp username=alice password=hunter2 --vault Personal
```

`get-field` prints the raw value (good for shell substitution); other commands print indented JSON.

## Limitations

- `create_item` and `update_item` pass field values as command-line assignment statements, so values may be visible to other processes via `ps` while `op` is running. Don't use it for highly sensitive values on shared hosts.
- Synchronous only — no async API.
- Relies on a signed-in `op` session; no built-in support for service-account tokens (yet).

## License

MIT — see [LICENSE](LICENSE).
