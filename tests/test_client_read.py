"""Tests for OnePasswordClient read methods."""

from __future__ import annotations

import json

import pytest

from onepwd import OnePasswordClient, OnePasswordError
from tests.conftest import FakeRun


def test_list_items_no_filters(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout=json.dumps([{"id": "abc", "title": "Example"}]))
    items = client.list_items()
    assert items == [{"id": "abc", "title": "Example"}]
    assert fake_run.last_call == ["op", "item", "list", "--format=json"]


def test_list_items_with_vault_and_categories(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(stdout="[]")
    client.list_items(vault="Personal", categories=["Login", "Database"])
    assert "--vault=Personal" in fake_run.last_call
    assert "--categories=Login,Database" in fake_run.last_call


def test_get_item(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout=json.dumps({"id": "x", "title": "GitHub"}))
    item = client.get_item("GitHub", vault="Work")
    assert item["title"] == "GitHub"
    assert fake_run.last_call[:5] == ["op", "item", "get", "GitHub", "--format=json"]
    assert "--vault=Work" in fake_run.last_call


def test_get_field_strips_whitespace_and_reveals(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(stdout="hunter2\n")
    value = client.get_field("GitHub", "password")
    assert value == "hunter2"
    assert fake_run.last_call[:5] == [
        "op",
        "item",
        "get",
        "GitHub",
        "--fields=password",
    ]
    assert "--reveal" in fake_run.last_call


def test_get_field_preserves_internal_whitespace(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    # op appends a trailing newline; only that is stripped. Whitespace that is
    # part of the secret itself must survive.
    fake_run.set_response(stdout="  pa ss \n")
    value = client.get_field("GitHub", "password")
    assert value == "  pa ss "


def test_get_field_strips_only_trailing_newline(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(stdout="secret\r\n")
    assert client.get_field("GitHub", "token") == "secret"


def test_get_multiple_fields_single_call(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(
        stdout=json.dumps(
            [
                {"id": "username", "label": "username", "value": "alice"},
                {"id": "password", "label": "password", "value": "hunter2"},
            ]
        )
    )
    result = client.get_multiple_fields("GitHub", ["username", "password"])
    assert result == {"username": "alice", "password": "hunter2"}
    assert len(fake_run.op_calls) == 1
    assert "--fields=username,password" in fake_run.last_call
    assert "--reveal" in fake_run.last_call
    assert "--format=json" in fake_run.last_call


def test_get_multiple_fields_handles_dict_payload(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(
        stdout=json.dumps({"id": "username", "label": "username", "value": "alice"})
    )
    result = client.get_multiple_fields("GitHub", ["username"])
    assert result == {"username": "alice"}


def test_get_multiple_fields_missing_field_is_none(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(
        stdout=json.dumps(
            [{"id": "username", "label": "username", "value": "alice"}]
        )
    )
    result = client.get_multiple_fields("GitHub", ["username", "missing"])
    assert result == {"username": "alice", "missing": None}


def test_get_multiple_fields_failure_falls_back_per_field(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    # Batched call rejects on unknown field; per-field fallback recovers the rest.
    fake_run.set_response(returncode=1, stderr="'b' isn't a field")
    fake_run.set_response(stdout="alice\n")  # get_field("a") succeeds
    fake_run.set_response(returncode=1, stderr="not a field")  # get_field("b") fails
    result = client.get_multiple_fields("Item", ["a", "b"])
    assert result == {"a": "alice", "b": None}


def test_get_multiple_fields_reraises_when_all_fallbacks_fail(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    # Batch fails AND every per-field read fails too — the signature of a real
    # error (missing item / expired session), not a single bad field name. The
    # original error must surface rather than being masked as all-None.
    fake_run.set_response(returncode=1, stderr="item not found")  # batch
    fake_run.set_response(returncode=1, stderr="item not found")  # get_field("a")
    fake_run.set_response(returncode=1, stderr="item not found")  # get_field("b")
    with pytest.raises(OnePasswordError, match="item not found"):
        client.get_multiple_fields("Missing", ["a", "b"])


def test_get_multiple_fields_empty_skips_call(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    assert client.get_multiple_fields("GitHub", []) == {}
    assert fake_run.op_calls == []


def test_non_zero_exit_raises(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(returncode=1, stderr="item not found")
    with pytest.raises(OnePasswordError, match="item not found"):
        client.get_item("Missing")


def test_malformed_json_raises(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout="not json{{{")
    with pytest.raises(OnePasswordError, match="parse op output"):
        client.list_items()
