"""Contract checks for one submission and same-ID task retrieval."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from client import SunoClient, SunoError


class FakeResponse:
    def __init__(self, payload: dict, trace: str = "") -> None:
        self.payload = payload
        self.headers = {"x-trace-id": trace}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return json.dumps(self.payload).encode()


@pytest.mark.asyncio
async def test_submit_once_returns_task_id_without_claiming_completion():
    calls = []

    def fake_open(request, timeout):
        calls.append((request.full_url, json.loads(request.data), timeout))
        return FakeResponse({"task_id": "task-123", "success": True}, "trace-123")

    with patch("client.OPENER.open", side_effect=fake_open):
        result = await SunoClient("test-key").submit(
            "A short piano melody", duration=10
        )

    assert calls == [
        (
            "https://api.acedata.cloud/suno/audios",
            {
                "action": "generate",
                "prompt": "A short piano melody",
                "instrumental": True,
                "model": "chirp-v6",
                "async": True,
                "duration": 10,
            },
            60,
        )
    ]
    assert result["status"] == "submitted"
    assert result["task_id"] == "task-123"
    assert result["trace_id"] == "trace-123"


@pytest.mark.asyncio
async def test_preview_stays_pending_then_same_id_yields_final_audio():
    calls = []
    responses = iter(
        [
            {
                "id": "task-123",
                "finished_at": None,
                "response": {
                    "state": "running",
                    "data": [{"audio_url": "https://example.org/preview.mp3"}],
                },
            },
            {
                "id": "task-123",
                "finished_at": "2026-10-11T00:00:00Z",
                "response": {
                    "state": "complete",
                    "success": True,
                    "data": [{"audio_url": "https://example.org/final.mp3"}],
                },
            },
        ]
    )

    def fake_open(request, timeout):
        calls.append(json.loads(request.data))
        return FakeResponse(next(responses))

    with patch("client.OPENER.open", side_effect=fake_open):
        client = SunoClient("test-key")
        pending = await client.query("task-123")
        completed = await client.query("task-123")

    assert calls == [{"action": "retrieve", "id": "task-123"}] * 2
    assert pending == {
        "task_id": "task-123",
        "trace_id": "",
        "status": "pending",
        "success": False,
        "audio_urls": [],
    }
    assert completed["status"] == "succeeded"
    assert completed["success"] is True
    assert completed["audio_urls"] == ["https://example.org/final.mp3"]


@pytest.mark.asyncio
async def test_failed_task_never_exposes_preview_url():
    body = {
        "finished_at": "2026-10-11T00:00:00Z",
        "response": {
            "state": "failed",
            "success": False,
            "data": [{"audio_url": "https://example.org/preview.mp3"}],
        },
    }
    with patch("client.OPENER.open", return_value=FakeResponse(body)):
        result = await SunoClient("test-key").query("task-123")
    assert result["status"] == "failed"
    assert result["audio_urls"] == []


@pytest.mark.asyncio
async def test_missing_task_id_does_not_repeat_generation():
    with (
        patch(
            "client.OPENER.open", return_value=FakeResponse({"success": True})
        ) as opening,
        pytest.raises(SunoError, match="No task ID"),
    ):
        await SunoClient("test-key").submit("Piano")
    assert opening.call_count == 1
