# AstrBot 的 Suno 插件

通过自己的 Ace Data Cloud 账号，在 AstrBot 聊天中生成 Suno 音乐。插件提供 `suno_generate_music` 提交任务与 `suno_get_task` 查询同一任务两个 Agent 工具。提交成功或出现试听链接不代表歌曲已完成。

[English guide](../README.md) · [Suno API](https://platform.acedata.cloud/documents/4da95d9d-7722-4a72-857d-bf6be86036e9?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=sunoastrbot_readme_documents_4da95d9d_7722_4a72_857d_bf6be86036e9) · [当前价格](https://platform.acedata.cloud/models?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=sunoastrbot_readme_pricing)

## 1. 搜索与安装

在 AstrBot WebUI 中打开 **Extensions → Plugins → AstrBot Plugin Market**，搜索 **Suno**。核对卡片名称 **Suno by Ace Data Cloud**、作者 **acedatacloud** 和 Suno 服务图标，然后打开详情并点击 **Install**。回到 **Installed**，确认插件已启用且没有加载错误。

插件已在 [AstrBot Cloud](https://cloud.astrbot.app/plugin/AceDataCloud/astrbot_plugin_suno_acedatacloud) 正式上架，推荐按上面的市场流程安装。也可通过 **Installed → Install (+) → Install from URL** 填入 `https://github.com/AceDataCloud/SunoAstrBot` 安装源码仓库；仓库安装是独立路径，不能代替市场安装验证。

## 2. 获取 Suno API Key

首次使用请先注册并登录；如果应用页还没有通用应用，点击 **初始化通用应用（Initialize General Application）**，再按下面步骤管理密钥。

登录 [Ace Data Cloud Applications](https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=sunoastrbot_readme_api_key)，打开 **General application** 复制现有 Key，或进入 **Manage Keys → Create** 创建 AstrBot 专用 Key。服务专用 Key 也可使用，但要同时允许 `/suno/audios` 与 `/suno/tasks`。生成前检查 Suno 当前价格与余额。

只复制 Key 本身，不加 `Bearer `，也不要使用 `platform-...` 管理 Token。不要把 Key 写进聊天消息或仓库文件。

## 3. 配置 AstrBot

在 **Extensions → Plugins → Installed** 中点击 **Suno by Ace Data Cloud** 的齿轮，将 Key 填入 **Ace Data Cloud generation API key with Suno access** 并保存。AstrBot WebUI 会遮蔽输入，但插件配置文件仍存储原值，应保护 AstrBot 数据目录。

选择支持工具调用的聊天模型，并在当前会话的 Profile 和 Persona 中允许 `suno_generate_music` 与 `suno_get_task`。工具未出现时查看 **Extensions → Handlers**。

## 4. 在聊天中只提交一次

在 AstrBot ChatUI 或已连接的聊天平台发送：

> 使用 `suno_generate_music` 生成一首日出主题的短钢琴纯音乐，`model` 为 `chirp-v6`，`duration` 为 `10`，`instrumental` 为 true。只提交一次，并告诉我返回的 task ID。

工具返回 `status: submitted` 和 `task_id`。保存这个 ID。时长是目标值，最终时长可能不同。插件不会自动换模型，也不会在网络异常时自动重复提交。

## 5. 查询同一任务

继续发送：

> 使用 `suno_get_task` 查询任务 ID `<刚才的 task_id>`，告诉我状态，不要再生成歌曲。

返回 `pending` 时稍后继续查**同一个 ID**。运行中的试听音频不算最终结果，插件不会返回它。只有 `status: succeeded` 且 `success: true` 才算完成。打开 `audio_urls` 中的链接试听。若模型试图再次提交，请停止并明确只调用 `suno_get_task`。

## 6. 核对账单与排障

在 Ace Data Cloud 的应用用量或账单记录中按 task/trace ID 核对。成功的音乐生成有自己的用量记录；任务查询读取已有结果。按服务页面的实时价格判断，不套用固定 Credits 或美元金额。

| 现象 | 检查项 |
| --- | --- |
| 插件加载失败 | AstrBot 版本、**Failed to Load Plugins**、**Data & Logs → Logs**。 |
| 看不到工具 | 插件已启用；当前 Profile 和 Persona 允许工具；聊天模型支持工具调用。 |
| HTTP 401/403 | Key 是允许 Suno 的生成 API Key；Allowed APIs 同时包含生成和查询路径。 |
| 提交后网络错误 | 先查 Ace 请求历史，再考虑重试；超时请求仍可能已创建任务。 |
| 任务 pending | 稍后继续查同一个 task ID，不重复调用生成工具。 |
| 任务 failed | 用 task/trace ID 查询服务请求历史与错误原因。 |

插件只向 `https://api.acedata.cloud` 发送 Key，不自动重试付费生成，只向模型返回状态和最终音频链接。使用 Python 标准库，无新增依赖。

## 已验证的本地运行

在隔离的 AstrBot `v4.28.2` 实例中，两个工具均注册成功。ChatUI 会话实际调用工具，只提交一次 `chirp-v6` 生成，并用同一 task ID 查询到 `succeeded`。两个最终 MP3 均解码为 18.024 秒音频。对应的一条 Suno API 用量记录显示原价 0.56 Credits、账户折扣后扣款 0.504 Credits。[脱敏证据](../tests/e2e-results.json)包含 task 与 trace ID。

## 已验证的市场安装

2026-10-12，[Cloud 公开卡片](https://cloud.astrbot.app/plugin/AceDataCloud/astrbot_plugin_suno_acedatacloud)显示版本 `0.1.0`。独立的全新 AstrBot `v4.28.2` 实例通过官方市场安装，读回 `install_method: market` 与 `activated: true`。ChatUI 仅调用一次 `suno_get_task` 查询已有成功任务，返回两个最终音频链接，没有再次生成。[脱敏市场证据](https://github.com/AceDataCloud/Index/blob/main/plans/ecosystem-growth/agent-provider-onboarding/execution/evidence/astrbot-market-20261012.json)记录安装与调用。

## 品牌素材

`logo.png` 是当前 [Suno 服务图标](https://cdn.acedata.cloud/l3ffw7.jpg) 的 PNG 编码，并非重新绘制。源 JPEG SHA-256：`d2ccb1c0039519a68913ad447114f8f9ecca161ffc2105cd61c414e06f8747d9`；打包 PNG SHA-256：`60794402c519a7d34bb50158d4442d0fbba814e3754a981bb5649468a1c8afc0`。
