"""Tests for callback client retry behavior."""

from __future__ import annotations

import httpx
import pytest

from validators.core import callback_client
from sv_shared.validations.envelopes import ValidationStatus


class _FakeResponse:
    def __init__(self, status_code: int, json_body=None, raise_for_status=None):
        self.status_code = status_code
        self._json_body = json_body or {}
        self._raise_for_status = raise_for_status

    def json(self):
        return self._json_body

    def raise_for_status(self):
        if self._raise_for_status:
            raise self._raise_for_status


def test_post_callback_retries_and_succeeds(monkeypatch):
    """post_callback should retry on transient HTTP errors."""
    calls = {"count": 0}

    monkeypatch.setattr(
        "validators.core.callback_client.id_token.fetch_id_token",
        lambda *_args, **_kwargs: "fake-id-token",
    )

    class _Client:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def post(self, *args, **kwargs):
            calls["count"] += 1
            # First attempt fails, second succeeds
            if calls["count"] == 1:
                exc = httpx.HTTPStatusError(
                    "fail", request=httpx.Request("POST", "http://x"), response=httpx.Response(500)
                )
                raise exc
            return _FakeResponse(200, json_body={"ok": True})

    monkeypatch.setattr(callback_client.httpx, "Client", _Client)

    resp = callback_client.post_callback(
        callback_url="http://example.com",
        callback_token="fake-token",
        run_id="1",
        status=ValidationStatus.SUCCESS,
        result_uri="gs://bucket/run/output.json",
        max_attempts=2,
        retry_delay_seconds=0,
    )

    assert resp == {"ok": True}
    assert calls["count"] == 2
