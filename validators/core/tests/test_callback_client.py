"""Tests for callback client retry behavior and callback_id handling."""

from __future__ import annotations

import httpx

from validators.core import callback_client
from vb_shared.validations.envelopes import ValidationStatus


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
                    "fail",
                    request=httpx.Request("POST", "http://x"),
                    response=httpx.Response(500),
                )
                raise exc
            return _FakeResponse(200, json_body={"ok": True})

    monkeypatch.setattr(callback_client.httpx, "Client", _Client)

    resp = callback_client.post_callback(
        callback_url="http://example.com",
        run_id="1",
        status=ValidationStatus.SUCCESS,
        result_uri="gs://bucket/run/output.json",
        max_attempts=2,
        retry_delay_seconds=0,
    )

    assert resp == {"ok": True}
    assert calls["count"] == 2


def test_post_callback_includes_callback_id_in_payload(monkeypatch):
    """post_callback should include callback_id in the POST payload for idempotency."""
    captured_payload = {}

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

        def post(self, url, json=None, **kwargs):
            captured_payload.update(json or {})
            return _FakeResponse(200, json_body={"ok": True})

    monkeypatch.setattr(callback_client.httpx, "Client", _Client)

    callback_id = "test-idempotency-key-12345"
    callback_client.post_callback(
        callback_url="http://example.com/callback",
        run_id="run-123",
        status=ValidationStatus.SUCCESS,
        result_uri="gs://bucket/run/output.json",
        callback_id=callback_id,
    )

    assert captured_payload["callback_id"] == callback_id
    assert captured_payload["run_id"] == "run-123"
    assert captured_payload["status"] == "success"
    assert captured_payload["result_uri"] == "gs://bucket/run/output.json"


def test_post_callback_without_callback_id(monkeypatch):
    """post_callback should work without callback_id (backwards compatibility)."""
    captured_payload = {}

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

        def post(self, url, json=None, **kwargs):
            captured_payload.update(json or {})
            return _FakeResponse(200, json_body={"ok": True})

    monkeypatch.setattr(callback_client.httpx, "Client", _Client)

    callback_client.post_callback(
        callback_url="http://example.com/callback",
        run_id="run-456",
        status=ValidationStatus.FAILED_VALIDATION,
        result_uri="gs://bucket/run/output.json",
        # callback_id not provided
    )

    assert captured_payload["callback_id"] is None
    assert captured_payload["run_id"] == "run-456"
    assert captured_payload["status"] == "failed_validation"


def test_post_callback_skip_callback_returns_none():
    """post_callback should return None when skip_callback=True."""
    result = callback_client.post_callback(
        callback_url="http://example.com/callback",
        run_id="run-789",
        status=ValidationStatus.SUCCESS,
        result_uri="gs://bucket/run/output.json",
        callback_id="some-id",
        skip_callback=True,
    )

    assert result is None


def test_post_callback_no_url_returns_none():
    """post_callback should return None when callback_url is None."""
    result = callback_client.post_callback(
        callback_url=None,
        run_id="run-abc",
        status=ValidationStatus.SUCCESS,
        result_uri="gs://bucket/run/output.json",
        callback_id="some-id",
    )

    assert result is None
