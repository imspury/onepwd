"""Tests for OnePasswordClient write methods + list_vaults."""

from __future__ import annotations

import json

import pytest

from onepwd import OnePasswordClient, OnePasswordError
from tests.conftest import FakeRun


def test_list_vaults(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout=json.dumps([{"id": "v1", "name": "Personal"}]))
    vaults = client.list_vaults()
    assert vaults[0]["name"] == "Personal"
    assert fake_run.last_call == ["op", "vault", "list", "--format=json"]


def test_create_item_sends_template_via_stdin(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(stdout=json.dumps({"id": "new"}))
    client.create_item(
        "login",
        "MyApp",
        fields={"username": "alice", "password": "hunter2"},
        vault="Personal",
        tags=["work", "mfa"],
    )
    call = fake_run.last_call
    assert call[:2] == ["op", "item"]
    assert "create" in call
    assert "--vault=Personal" in call
    assert "--tags=work,mfa" in call
    assert "--format=json" in call
    # When using a stdin template, --category/--title live in the template,
    # not on argv (op rejects them as a conflict).
    assert "--category=login" not in call
    assert "--title=MyApp" not in call
    # Secrets must NOT appear on argv — they ride on stdin.
    assert "password=hunter2" not in call
    assert "hunter2" not in " ".join(call)
    assert "--template=-" not in call  # op reads stdin implicitly
    # Template arrives on stdin with a CONCEALED password and STRING username.
    assert fake_run.last_input is not None
    template = json.loads(fake_run.last_input)
    assert template["title"] == "MyApp"
    assert template["category"] == "LOGIN"
    by_label = {f["label"]: f for f in template["fields"]}
    # Built-in slots get a `purpose` so op fills them in instead of adding
    # duplicate custom fields. They do NOT carry an explicit `type`.
    assert by_label["password"]["value"] == "hunter2"
    assert by_label["password"]["purpose"] == "PASSWORD"
    assert "type" not in by_label["password"]
    assert by_label["username"]["value"] == "alice"
    assert by_label["username"]["purpose"] == "USERNAME"
    assert "type" not in by_label["username"]


def test_create_item_concealed_label_hints(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(stdout=json.dumps({"id": "new"}))
    client.create_item(
        "api_credential",
        "ServiceX",
        fields={"api_key": "k", "endpoint": "https://x"},
    )
    template = json.loads(fake_run.last_input)
    by_label = {f["label"]: f for f in template["fields"]}
    # Labels without a built-in purpose fall back to type heuristics.
    assert by_label["api_key"]["type"] == "CONCEALED"
    assert "purpose" not in by_label["api_key"]
    assert by_label["endpoint"]["type"] == "STRING"
    assert "purpose" not in by_label["endpoint"]


def test_create_item_notes_gets_purpose(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(stdout=json.dumps({"id": "new"}))
    client.create_item("login", "MyApp", fields={"notes": "free-form text"})
    template = json.loads(fake_run.last_input)
    by_label = {f["label"]: f for f in template["fields"]}
    assert by_label["notes"]["purpose"] == "NOTES"
    assert "type" not in by_label["notes"]


def test_create_item_minimal_no_template(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(stdout=json.dumps({"id": "new"}))
    client.create_item("password", "Foo")
    call = fake_run.last_call
    assert "--vault=" not in " ".join(call)
    assert all(not c.startswith("--tags=") for c in call)
    # No fields → no template, so --category/--title pass on argv as before.
    assert "--category=password" in call
    assert "--title=Foo" in call
    assert fake_run.last_input is None


def test_update_item(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout=json.dumps({"id": "x"}))
    client.update_item("MyApp", {"password": "newpass"}, vault="Personal")
    call = fake_run.last_call
    assert call[:4] == ["op", "item", "edit", "MyApp"]
    assert "password=newpass" in call
    assert "--vault=Personal" in call
    assert "--format=json" in call


def test_update_item_redacts_secrets_in_errors(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(returncode=1, stderr="permission denied")
    with pytest.raises(OnePasswordError) as exc:
        client.update_item("MyApp", {"password": "hunter2"})
    msg = str(exc.value)
    assert "hunter2" not in msg
    assert "password=***" in msg
    # Long flags stay verbatim — they're not secrets.
    assert "--format=json" in msg


def test_delete_item(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response()
    client.delete_item("MyApp", vault="Personal")
    call = fake_run.last_call
    assert call[:4] == ["op", "item", "delete", "MyApp"]
    assert "--vault=Personal" in call
    assert "--archive" not in call


def test_delete_item_archive(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response()
    client.delete_item("MyApp", archive=True)
    assert "--archive" in fake_run.last_call
