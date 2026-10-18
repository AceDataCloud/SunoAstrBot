"""Suno music tools for AstrBot through Ace Data Cloud."""

from __future__ import annotations

import json

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .client import SunoClient, SunoError


class SunoPlugin(Star):
    """Expose one generation tool and one task lookup tool to chat agents."""

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        """Initialize the plugin with AstrBot's masked-key configuration.

        Args:
            context: AstrBot plugin context.
            config: Plugin configuration from the dashboard.
        """
        super().__init__(context)
        self.config = config

    @filter.llm_tool(name="suno_generate_music")
    async def suno_generate_music(
        self,
        event: AstrMessageEvent,
        prompt: str,
        instrumental: bool = True,
        duration: int = 0,
        model: str = "chirp-v6",
    ) -> str:
        """Submit one Suno music generation. Save the task ID and query it for final audio.

        Args:
            prompt(string): Description of the desired music.
            instrumental(boolean): True for music without vocals.
            duration(number): Optional target seconds, 10 to 360; 0 lets Suno choose.
            model(string): chirp-v6, chirp-v6-mini, or chirp-v6-wild.

        Returns:
            JSON with submission status and task ID, never a completed-audio claim.
        """
        try:
            result = await SunoClient(self.config.get("api_key", "")).submit(
                prompt, instrumental, duration, model
            )
        except SunoError as exc:
            result = {"status": "error", "message": str(exc)}
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="suno_get_task")
    async def suno_get_task(self, event: AstrMessageEvent, task_id: str) -> str:
        """Query a previous Suno task ID without paying for another generation.

        Args:
            task_id(string): Exact task ID from suno_generate_music.

        Returns:
            JSON status and final audio URLs only after terminal success.
        """
        try:
            result = await SunoClient(self.config.get("api_key", "")).query(task_id)
        except SunoError as exc:
            result = {"status": "error", "message": str(exc), "task_id": task_id}
        return json.dumps(result, ensure_ascii=False)

    @filter.command("suno_ace")
    async def suno_ace_help(self, event: AstrMessageEvent):
        """Show Suno setup and existing-task help without an API call."""
        yield event.plain_result(
            "Suno by Ace Data Cloud / Ace Data Cloud 提供的 Suno 集成\nSetup / 配置：Plugins → Plugins → Installed → plugin gear / 插件 → 插件 → 已安装 → 齿轮。\nRegister/sign in / 注册登录：https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=sunoastrbot_command_help\nGeneral application → Manage Keys → Create；首次先初始化通用应用。\nAllow APIs / 允许接口：/suno/audios + /suno/tasks。检查当前权限、余额和价格。\nPaste the API Key in plugin settings only, never in chat. / 只在插件设置填 Key，不在聊天发送密钥。\nAdmin existing-task lookup / 管理员查已有任务：/suno_ace_task <task_id>\nAgent lookup tool / Agent 查询工具：suno_get_task；生成只调用一次，pending 时继续查同一 ID。\nGuide / 指南：https://github.com/AceDataCloud/SunoAstrBot#readme"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("suno_ace_task")
    async def suno_ace_task(self, event: AstrMessageEvent, task_id: str):
        """Let administrators retrieve one existing task without an LLM or generation."""
        try:
            result = await SunoClient(self.config.get("api_key", "")).query(task_id)
        except SunoError as exc:
            result = {"status": "error", "message": str(exc), "task_id": task_id}
        yield event.plain_result(json.dumps(result, ensure_ascii=False))
