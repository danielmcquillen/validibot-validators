"""
HTTP callback client for validator containers.

Provides utilities for POSTing validation completion callbacks back to the
Cloud Run Service (Django).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

from validibot_shared.validations.envelopes import ValidationCallback, ValidationStatus


logger = logging.getLogger(__name__)


def post_callback(
    callback_url: str | None,
    run_id: str,
    status: ValidationStatus,
    result_uri: str,
    *,
    callback_id: str | None = None,
    skip_callback: bool = False,
    timeout_seconds: int = 30,
    max_attempts: int = 3,
    retry_delay_seconds: float = 1.0,
) -> dict[str, Any] | None:
    """
    POST a validation completion callback to the Cloud Run Service.

    Args:
        callback_url: Django callback endpoint URL (can be None if skip_callback=True)
        run_id: Validation run ID
        status: Validation status (SUCCESS, FAILED_VALIDATION, etc.)
        result_uri: GCS URI to output.json
        callback_id: Idempotency key echoed from the input envelope (for duplicate detection)
        skip_callback: If True, skip the callback POST (useful for testing)
        timeout_seconds: HTTP request timeout
        max_attempts: Retry attempts for transient failures
        retry_delay_seconds: Delay between retries

    Returns:
        Response JSON from Django, or None if skip_callback=True

    Raises:
        httpx.HTTPStatusError: If callback request fails
    """
    if skip_callback:
        logger.info("Skipping callback for run_id=%s (skip_callback=True)", run_id)
        return None

    if not callback_url:
        logger.warning(
            "No callback_url provided for run_id=%s and skip_callback=False; skipping",
            run_id,
        )
        return None

    logger.info(
        "POSTing callback for run_id=%s to %s (callback_id=%s)",
        run_id,
        callback_url,
        callback_id,
    )

    callback = ValidationCallback(
        run_id=run_id,
        callback_id=callback_id,
        status=status,
        result_uri=result_uri,
    )

    def _build_headers() -> dict[str, str]:
        """
        Prefer an ID token minted from the runtime service account (Cloud Run Job).
        Continue without Authorization header when running locally and metadata
        server access is unavailable.
        """
        headers = {
            "Content-Type": "application/json",
        }
        audience = callback_url
        try:
            token = id_token.fetch_id_token(GoogleAuthRequest(), audience)
            headers["Authorization"] = f"Bearer {token}"
        except Exception:
            logger.warning(
                "Failed to fetch ID token; sending callback without Authorization header",
                exc_info=True,
            )
        return headers

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            headers = _build_headers()
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(
                    callback_url,
                    json=callback.model_dump(),
                    headers=headers,
                )

                response.raise_for_status()

                logger.info(
                    "Callback successful (run_id=%s, status=%d)",
                    run_id,
                    response.status_code,
                )

                return response.json()
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning(
                "Callback attempt %d/%d failed: %s",
                attempt,
                max_attempts,
                exc,
            )
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)
            else:
                raise

    if last_exc:
        raise last_exc
