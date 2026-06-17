"""Tests for OnePasswordClient write methods + list_vaults."""

from __future__ import annotations

import json

from onepwd import OnePasswordClient
from tests.conftest import FakeRun


def test_list_vaults(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout=json.dumps([{"id": "v1", "name": "Personal"}]))
    vaults = client.list_vaults()
    assert vaults[0]["name"] == "Personal"
    assert fake_run.last_call == ["op", "vault", "list", "--format=json"]


def test_create_item_basic(client: OnePasswordClient, fake_run: FakeRun) -> None:
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
    assert "--category=login" in call
    assert "--title=MyApp" in call
    assert "--vault=Personal" in call
    assert "--tags=work,mfa" in call
    assert "--format=json" in call
    assert "username=alice" in call
    assert "password=hunter2" in call


def test_create_item_minimal(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout=json.dumps({"id": "new"}))
    client.create_item("password", "Foo")
    call = fake_run.last_call
    assert "--vault=" not in " ".join(call)  # no vault flag
    assert all(not c.startswith("--tags=") for c in call)


def test_update_item(client: OnePasswordClient, fake_run: FakeRun) -> None:
    fake_run.set_response(stdout=json.dumps({"id": "x"}))
    client.update_item("MyApp", {"password": "newpass"}, vault="Personal")
    call = fake_run.last_call
    assert call[:4] == ["op", "item", "edit", "MyApp"]
    assert "password=newpass" in call
    assert "--vault=Personal" in call
    assert "--format=json" in call


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
