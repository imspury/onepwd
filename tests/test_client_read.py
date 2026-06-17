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


def test_get_field_strips_whitespace(client: OnePasswordClient, fake_run: FakeRun) -> None:
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


def test_get_multiple_fields_aggregates(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout="alice\n")
    fake_run.set_response(stdout="hunter2\n")
    result = client.get_multiple_fields("GitHub", ["username", "password"])
    assert result == {"username": "alice", "password": "hunter2"}


def test_get_multiple_fields_returns_none_on_failure(
    client: OnePasswordClient, fake_run: FakeRun
) -> None:
    fake_run.set_response(stdout="alice\n")
    fake_run.set_response(returncode=1, stderr="no such field")
    result = client.get_multiple_fields("GitHub", ["username", "missing"])
    assert result == {"username": "alice", "missing": None}


def test_non_zero_exit_raises(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(returncode=1, stderr="item not found")
    with pytest.raises(OnePasswordError, match="item not found"):
        client.get_item("Missing")


def test_malformed_json_raises(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout="not json{{{")
    with pytest.raises(OnePasswordError, match="parse op output"):
        client.list_items()
