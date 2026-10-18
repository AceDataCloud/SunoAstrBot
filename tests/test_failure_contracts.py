"""Failure/cancellation contracts: no preview, retry, or leaked credential."""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError

import pytest

from client import SunoClient, SunoError


class Response:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return json.dumps(self.payload).encode()


@pytest.mark.asyncio
@pytest.mark.parametrize("finished_at", [None, 123.0])
async def test_cancelled_task_is_terminal_without_media_even_before_finished_timestamp(
    finished_at,
):
    body = {
        "finished_at": finished_at,
        "response": {
            "state": "cancelled",
            "success": True,
            "data": [{"audio_url": "https://example.org/preview.mp3"}],
        },
    }
    with patch("client.OPENER.open", return_value=Response(body)) as opening:
        result = await SunoClient("test-key").query("original-task")
    assert result["status"] == "failed"
    assert result["success"] is False
    assert not result["audio_urls"]
    assert opening.call_count == 1
    assert json.loads(opening.call_args.args[0].data) == {
        "action": "retrieve",
        "id": "original-task",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_http_error_preserves_status_without_leaking_secret_or_retrying(status):
    response = HTTPError(
        "https://api.acedata.cloud/tasks",
        status,
        "upstream-private-detail",
        {},
        BytesIO(b"private-key-value and upstream detail"),
    )
    with (
        patch("client.OPENER.open", side_effect=response) as opening,
        pytest.raises(SunoError) as raised,
    ):
        await SunoClient("private-key-value").query("original-task")
    assert f"HTTP {status}" in str(raised.value)
    assert "private-key-value" not in str(raised.value)
    assert "upstream-private-detail" not in str(raised.value)
    assert opening.call_count == 1


@pytest.mark.asyncio
async def test_local_coroutine_cancellation_propagates_without_second_request():
    # Cancellation stops waiting locally; it does not cancel an upstream job.
    with (
        patch(
            "client.asyncio.to_thread",
            new=AsyncMock(side_effect=asyncio.CancelledError),
        ) as transport,
        pytest.raises(asyncio.CancelledError),
    ):
        await SunoClient("test-key").query("original-task")
    assert transport.await_count == 1
