"""Reproduce no-network native registration/permission checks with real AstrBot.

Run from an isolated environment containing astrbot==4.29.0:
    python scripts/verify_host.py

No Key is needed. This checks real host decorators and permission filters,
not a full dashboard install, message dispatcher, live API, or LLM loop.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import importlib.util
import inspect
import json
import os
import socket
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import AsyncMock, patch


async def collect(generator):
    return [item async for item in generator]


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="ace-astrbot-host-") as temporary:
        previous_cwd = os.getcwd()
        os.chdir(temporary)
        try:
            import yaml
            from astrbot.api import AstrBotConfig
            from astrbot.api.event import filter
            from astrbot.api.star import Star
            from astrbot.core.star.filter.command import CommandFilter
            from astrbot.core.star.filter.permission import PermissionTypeFilter

            network_attempts = []

            def block_network(*_args, **_kwargs):
                network_attempts.append(True)
                raise AssertionError("No network request is allowed")

            with (
                patch.object(socket.socket, "connect", block_network),
                patch.object(socket, "create_connection", block_network),
            ):
                name = "ace_verified_plugin"
                package = types.ModuleType(name)
                package.__path__ = [str(root)]
                sys.modules[name] = package
                spec = importlib.util.spec_from_file_location(
                    name + ".main", root / "main.py"
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                plugin_type = next(
                    value
                    for value in vars(module).values()
                    if inspect.isclass(value)
                    and value is not Star
                    and issubclass(value, Star)
                    and value.__module__ == spec.name
                )
                client_module = sys.modules[name + ".client"]
                client_type = next(
                    value
                    for value in vars(client_module).values()
                    if inspect.isclass(value) and value.__name__.endswith("Client")
                )
                schema = json.loads((root / "_conf_schema.json").read_text())
                assert schema["api_key"]["secret"] is True
                assert schema["api_key"]["default"] == ""
                config = AstrBotConfig(
                    config_path=str(Path(temporary) / "plugin.json"),
                    default_config={"api_key": ""},
                )
                plugin = plugin_type(None, config)

                class Event:
                    def __init__(self, admin=False):
                        self.admin = admin

                    def is_admin(self):
                        return self.admin

                    def plain_result(self, text):
                        return text

                help_method = next(
                    getattr(plugin, key)
                    for key in plugin_type.__dict__
                    if key.endswith("_ace_help")
                )
                task_method = next(
                    getattr(plugin, key)
                    for key in plugin_type.__dict__
                    if key.endswith("_ace_task")
                )
                metadata_for = filter.command.__globals__["get_handler_or_create"]
                event_type = filter.command.__globals__["EventType"].AdapterMessageEvent
                help_md = metadata_for(help_method.__func__, event_type)
                task_md = metadata_for(task_method.__func__, event_type)
                help_filter = next(
                    f for f in help_md.event_filters if isinstance(f, CommandFilter)
                )
                task_filter = next(
                    f for f in task_md.event_filters if isinstance(f, CommandFilter)
                )
                permission = next(
                    f
                    for f in task_md.event_filters
                    if isinstance(f, PermissionTypeFilter)
                )
                assert permission.filter(Event(False), config) is False
                assert permission.filter(Event(True), config) is True
                assert task_filter.validate_and_convert_params(
                    ["original-task"], task_filter.handler_params
                ) == {"task_id": "original-task"}
                with patch.object(client_type, "query", new=AsyncMock()) as query:
                    text = asyncio.run(collect(help_method(Event())))[0]
                    assert "Ace Data Cloud" in text
                    query.assert_not_called()
                empty_key = json.loads(
                    asyncio.run(collect(task_method(Event(True), "original-task")))[0]
                )
                assert (
                    empty_key["status"] == "error"
                    and "key" in empty_key["message"].lower()
                )
                config["api_key"] = "local-test-placeholder"
                with (
                    patch.object(
                        client_type,
                        "query",
                        new=AsyncMock(side_effect=asyncio.CancelledError),
                    ) as query,
                    patch.object(client_type, "submit", new=AsyncMock()) as submit,
                ):
                    try:
                        asyncio.run(collect(task_method(Event(True), "original-task")))
                    except asyncio.CancelledError:
                        pass
                    else:
                        raise AssertionError("Local cancellation was swallowed")
                    query.assert_awaited_once_with("original-task")
                    submit.assert_not_called()
                config["api_key"] = ""
                manager = filter.llm_tool.__globals__["llm_tools"]
                tools = [
                    t.name
                    for t in manager.func_list
                    if t.handler.__module__ == spec.name
                ]
                assert len(tools) == 2
                assert not network_attempts
                meta = yaml.safe_load((root / "metadata.yaml").read_text())
                print(
                    json.dumps(
                        {
                            "plugin_id": meta["name"],
                            "package_version": str(meta["version"]),
                            "astrbot_version": importlib.metadata.version("astrbot"),
                            "commands": [
                                help_filter.command_name,
                                task_filter.command_name,
                            ],
                            "tools": tools,
                            "admin_allowed": True,
                            "non_admin_denied": True,
                            "secret_field": True,
                            "missing_key_rejected_locally": True,
                            "local_cancellation_propagates": True,
                            "generation_calls": 0,
                            "network_attempts": len(network_attempts),
                            "limits": "Real decorators/filters/handler bodies; fake events and mocked cancellation. No full dispatcher, browser, live task request or LLM.",
                        },
                        ensure_ascii=False,
                    )
                )
        finally:
            os.chdir(previous_cwd)


if __name__ == "__main__":
    main()
