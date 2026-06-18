"""Tests for OnePasswordClient construction, signin, and context manager."""

from __future__ import annotations

import subprocess

import pytest

from onepwd import OnePasswordClient, OnePasswordError
from tests.conftest import FakeRun


def test_init_constructs_when_signed_in(fake_run: FakeRun) -> None:
    fake_run.set_responses(
        {"stdout": "2.29.0\n"},
        {"stdout": "Email: a@b.com\nUser ID: U1\n"},
    )
    client = OnePasswordClient(auto_signin=False)
    assert isinstance(client, OnePasswordClient)
    assert fake_run.calls[0][:2] == ["op", "--version"]
    assert fake_run.calls[1][:2] == ["op", "whoami"]


def test_init_raises_when_op_not_installed(fake_run: FakeRun) -> None:
    fake_run.raises = FileNotFoundError("op")
    with pytest.raises(OnePasswordError, match="not found"):
        OnePasswordClient(auto_signin=False)


def test_init_raises_when_not_signed_in(fake_run: FakeRun) -> None:
    fake_run.set_response(stdout="2.29.0\n")
    fake_run.set_response(returncode=1, stderr="You are not currently signed in.")
    with pytest.raises(OnePasswordError, match="Not signed in"):
        OnePasswordClient(auto_signin=False)


def test_init_distinguishes_other_whoami_failures(fake_run: FakeRun) -> None:
    fake_run.set_response(stdout="2.29.0\n")
    fake_run.set_response(returncode=1, stderr="connection refused")
    with pytest.raises(OnePasswordError, match="whoami") as exc:
        OnePasswordClient(auto_signin=False)
    assert "Not signed in" not in str(exc.value)


def test_init_auto_signin_invokes_op_signin(fake_run: FakeRun) -> None:
    fake_run.set_response(stdout="2.29.0\n")
    fake_run.set_response(returncode=1, stderr="You are not currently signed in.")
    fake_run.set_response()  # `op signin` succeeds
    OnePasswordClient(auto_signin=True)
    signin_call = fake_run.calls[-1]
    assert signin_call[:2] == ["op", "signin"]


def test_auto_signin_propagates_failure(fake_run: FakeRun) -> None:
    fake_run.set_response(stdout="2.29.0\n")
    fake_run.set_response(returncode=1, stderr="You are not currently signed in.")
    fake_run.set_response(returncode=1, stderr="signin error")
    with pytest.raises(OnePasswordError, match="Failed to sign in"):
        OnePasswordClient(auto_signin=True)


def test_context_manager_returns_self_and_exits_clean(client: OnePasswordClient) -> None:
    with client as c:
        assert c is client
    # exiting twice without raising
    assert client.__exit__(None, None, None) is None


def test_check_cli_called_process_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> object:
        raise subprocess.CalledProcessError(1, ["op", "--version"])

    monkeypatch.setattr("onepwd.client.subprocess.run", boom)
    with pytest.raises(OnePasswordError, match="failed to run"):
        OnePasswordClient(auto_signin=False)
