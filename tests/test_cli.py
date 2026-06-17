"""Tests for the onepwd CLI entry point."""

from __future__ import annotations

import json

import pytest

from onepwd import __version__, cli
from onepwd.exceptions import OnePasswordError
from tests.conftest import FakeRun


def _prime_signin(fake_run: FakeRun) -> None:
    """Queue the two responses needed by OnePasswordClient.__init__."""
    fake_run.set_responses(
        {"stdout": "2.29.0\n"},
        {"stdout": "Email: a@b.com\nUser ID: U1\n"},
    )


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_list_prints_json(
    fake_run: FakeRun, capsys: pytest.CaptureFixture[str]
) -> None:
    _prime_signin(fake_run)
    fake_run.set_response(stdout=json.dumps([{"id": "x", "title": "T"}]))
    rc = cli.main(["--no-signin", "list", "--vault", "V"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["title"] == "T"


def test_get_field_prints_raw_string(
    fake_run: FakeRun, capsys: pytest.CaptureFixture[str]
) -> None:
    _prime_signin(fake_run)
    fake_run.set_response(stdout="hunter2\n")
    rc = cli.main(["--no-signin", "get-field", "GitHub", "password"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == "hunter2"


def test_create_passes_assignments(
    fake_run: FakeRun, capsys: pytest.CaptureFixture[str]
) -> None:
    _prime_signin(fake_run)
    fake_run.set_response(stdout=json.dumps({"id": "new"}))
    rc = cli.main(
        [
            "--no-signin",
            "create",
            "login",
            "MyApp",
            "username=alice",
            "password=hunter2",
            "--vault",
            "Personal",
        ]
    )
    assert rc == 0
    last = fake_run.last_call
    assert "username=alice" in last
    assert "password=hunter2" in last
    assert "--category=login" in last


def test_error_exits_nonzero(
    fake_run: FakeRun, capsys: pytest.CaptureFixture[str]
) -> None:
    _prime_signin(fake_run)
    fake_run.set_response(returncode=1, stderr="boom")
    rc = cli.main(["--no-signin", "list"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "boom" in err


def test_create_rejects_bad_assignment(
    fake_run: FakeRun, capsys: pytest.CaptureFixture[str]
) -> None:
    _prime_signin(fake_run)
    rc = cli.main(["--no-signin", "create", "login", "MyApp", "noequalsign"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "expected field=value" in err


def test_no_signin_flag_disables_auto_signin(
    fake_run: FakeRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--no-signin should mean auto_signin=False on the client."""
    captured: dict[str, bool] = {}

    real_init = cli.OnePasswordClient.__init__

    def spy(self: cli.OnePasswordClient, auto_signin: bool = False) -> None:
        captured["auto_signin"] = auto_signin
        real_init(self, auto_signin=auto_signin)

    monkeypatch.setattr(cli.OnePasswordClient, "__init__", spy)
    _prime_signin(fake_run)
    fake_run.set_response(stdout="[]")
    cli.main(["--no-signin", "list-vaults"])
    assert captured["auto_signin"] is False


def test_assignment_without_eq_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(OnePasswordError):
        cli._parse_assignments(["broken"])
