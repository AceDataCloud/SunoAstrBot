"""Native commands must not generate or expose the configured secret."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def loaded(monkeypatch):
    """Exercise command bodies without making AstrBot a runtime test dependency."""
    api = types.ModuleType("astrbot.api")
    api.AstrBotConfig = dict
    event_api = types.ModuleType("astrbot.api.event")
    event_api.AstrMessageEvent = object

    def decorator(*_args, **_kwargs):
        return lambda fn: fn

    event_api.filter = types.SimpleNamespace(
        llm_tool=decorator,
        command=decorator,
        permission_type=decorator,
        PermissionType=types.SimpleNamespace(ADMIN="admin"),
    )
    star_api = types.ModuleType("astrbot.api.star")

    class Star:
        def __init__(self, *_args, **_kwargs):
            pass

    star_api.Star = Star
    star_api.Context = object
    for name, module in {
        "astrbot": types.ModuleType("astrbot"),
        "astrbot.api": api,
        "astrbot.api.event": event_api,
        "astrbot.api.star": star_api,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    root = Path(__file__).resolve().parents[1]
    package_name = "ace_command_test_plugin"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    monkeypatch.setitem(sys.modules, package_name, package)
    spec = importlib.util.spec_from_file_location(
        package_name + ".main", root / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    client_module = sys.modules[package_name + ".client"]
    plugin = module.SunoPlugin(None, {"api_key": "configured-secret-never-echo"})
    yield (
        plugin,
        client_module.SunoClient,
        client_module.SunoError,
    )
    sys.modules.pop(package_name + ".client", None)


class Event:
    def plain_result(self, text):
        return text


@pytest.mark.asyncio
async def test_help_is_local_and_never_echoes_key(loaded, monkeypatch):
    plugin, client, _ = loaded
    query = AsyncMock(side_effect=AssertionError("help must not query"))
    submit = AsyncMock(side_effect=AssertionError("help must not generate"))
    monkeypatch.setattr(client, "query", query)
    monkeypatch.setattr(client, "submit", submit)
    responses = [x async for x in plugin.suno_ace_help(Event())]
    assert len(responses) == 1
    assert "Suno by Ace Data Cloud" in responses[0]
    assert "/suno_ace_task <task_id>" in responses[0]
    assert "configured-secret-never-echo" not in responses[0]
    assert "utm_content=sunoastrbot_command_help" in responses[0]
    query.assert_not_called()
    submit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "failed", "succeeded"])
async def test_task_command_queries_same_id_once_without_generating(
    loaded, monkeypatch, status
):
    plugin, client, _ = loaded
    payload = {
        "task_id": "original-task",
        "status": status,
        "success": status == "succeeded",
    }
    query = AsyncMock(return_value=payload)
    submit = AsyncMock(side_effect=AssertionError("query command must not generate"))
    monkeypatch.setattr(client, "query", query)
    monkeypatch.setattr(client, "submit", submit)
    responses = [x async for x in plugin.suno_ace_task(Event(), "original-task")]
    assert [json.loads(x) for x in responses] == [payload]
    query.assert_awaited_once_with("original-task")
    submit.assert_not_called()
    assert "configured-secret-never-echo" not in responses[0]


@pytest.mark.asyncio
async def test_task_error_keeps_id_without_retry_or_generation(loaded, monkeypatch):
    plugin, client, error = loaded
    query = AsyncMock(side_effect=error("Check service access"))
    submit = AsyncMock(side_effect=AssertionError("error must not generate"))
    monkeypatch.setattr(client, "query", query)
    monkeypatch.setattr(client, "submit", submit)
    responses = [x async for x in plugin.suno_ace_task(Event(), "original-task")]
    assert json.loads(responses[0]) == {
        "status": "error",
        "message": "Check service access",
        "task_id": "original-task",
    }
    query.assert_awaited_once_with("original-task")
    submit.assert_not_called()
    assert "configured-secret-never-echo" not in responses[0]
