"""Shared pytest fixtures for onepwd tests."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from onepwd.client import OnePasswordClient


@dataclass
class FakeRun:
    """Records calls to subprocess.run and returns scripted responses.

    Use ``set_response`` to queue the next response, or ``set_responses`` for
    a sequence (useful when a single test triggers multiple subprocess calls).
    """

    responses: list[subprocess.CompletedProcess] = field(default_factory=list)
    calls: list[list[str]] = field(default_factory=list)
    raises: BaseException | None = None

    def set_response(
        self, *, stdout: str = "", stderr: str = "", returncode: int = 0
    ) -> None:
        self.responses.append(
            subprocess.CompletedProcess(
                args=[], returncode=returncode, stdout=stdout, stderr=stderr
            )
        )

    def set_responses(self, *responses: dict[str, Any]) -> None:
        for r in responses:
            self.set_response(**r)

    def __call__(self, cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        self.calls.append(list(cmd))
        if self.raises is not None:
            raise self.raises
        if not self.responses:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        response = self.responses.pop(0)
        if kwargs.get("check") and response.returncode != 0:
            raise subprocess.CalledProcessError(
                response.returncode, cmd, response.stdout, response.stderr
            )
        return response

    @property
    def last_call(self) -> list[str]:
        return self.calls[-1]

    @property
    def op_calls(self) -> list[list[str]]:
        """Calls that invoked `op` (the first arg is 'op')."""
        return [c for c in self.calls if c and c[0] == "op"]


@pytest.fixture
def fake_run(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeRun]:
    """Patch subprocess.run in both call sites onepwd uses."""
    fake = FakeRun()
    # _process.subprocess.run is the chokepoint for read/write methods.
    monkeypatch.setattr("onepwd._process.subprocess.run", fake)
    # client.subprocess.run is used by _check_cli_installed and _perform_signin.
    monkeypatch.setattr("onepwd.client.subprocess.run", fake)
    yield fake


@pytest.fixture
def client(fake_run: FakeRun) -> OnePasswordClient:
    """Construct a client with auto_signin=False, with subprocess mocked.

    Queues the two responses needed by ``_check_cli_installed``: ``op --version``
    and ``op whoami``.
    """
    fake_run.set_responses(
        {"stdout": "2.29.0\n"},
        {"stdout": "Email: user@example.com\nUser ID: ABC123\n"},
    )
    c = OnePasswordClient(auto_signin=False)
    fake_run.calls.clear()  # discard init noise so tests can inspect their own calls
    return c
