"""Current model coverage at the real transport boundary, without API calls."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from test_client import FakeResponse

from client import MODELS, SunoClient

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "contracts/suno-models.json").read_text())


def test_generated_model_list_and_tool_description_match_public_contract():
    subprocess.run(
        [sys.executable, "scripts/sync_suno_models.py", "--check"], cwd=ROOT, check=True
    )
    assert MODELS == set(CONTRACT["models"])
    assert len(MODELS) == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("model", CONTRACT["models"])
async def test_each_public_model_makes_one_exact_generate_request(model):
    with patch(
        "client.OPENER.open", return_value=FakeResponse({"task_id": "offline-task"})
    ) as request:
        result = await SunoClient("offline-placeholder").submit(
            "Offline fixture", instrumental=False, duration=18, model=model
        )
    request.assert_called_once()
    sent = request.call_args.args[0]
    assert sent.full_url == "https://api.acedata.cloud/suno/audios"
    assert json.loads(sent.data) == {
        "action": "generate",
        "prompt": "Offline fixture",
        "instrumental": False,
        "duration": 18,
        "model": model,
        "async": True,
    }
    assert result["task_id"] == "offline-task"


@pytest.mark.asyncio
async def test_existing_default_and_omitted_duration_are_unchanged():
    with patch(
        "client.OPENER.open", return_value=FakeResponse({"task_id": "offline-task"})
    ) as request:
        await SunoClient("offline-placeholder").submit("Offline fixture")
    body = json.loads(request.call_args.args[0].data)
    assert body["model"] == "chirp-v6"
    assert body["instrumental"] is True
    assert "duration" not in body
