# Suno for AstrBot

Generate Suno music in an AstrBot conversation through your own Ace Data Cloud account. The plugin registers two agent tools: `suno_generate_music` submits one job, and `suno_get_task` retrieves that same job until it completes. A submitted job or a preview audio URL is not a finished song.

[简体中文指南](readme/README_zh_Hans.md) · [Suno API](https://platform.acedata.cloud/documents/4da95d9d-7722-4a72-857d-bf6be86036e9?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=sunoastrbot_readme_documents_4da95d9d_7722_4a72_857d_bf6be86036e9) · [Current prices](https://platform.acedata.cloud/models?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=sunoastrbot_readme_pricing)

## 1. Find and install

In AstrBot WebUI, open **Extensions → Plugins → AstrBot Plugin Market** and search **Suno**. Check the card says **Suno by Ace Data Cloud**, the author is **acedatacloud**, and the logo matches the Suno service icon. Open the details and select **Install**. Once installed, find it under **Installed** and confirm that it is enabled without a load error.

The plugin is published in [AstrBot Cloud](https://cloud.astrbot.app/plugin/AceDataCloud/astrbot_plugin_suno_acedatacloud). Prefer the market installation above. **Installed → Install (+) → Install from URL** with `https://github.com/AceDataCloud/SunoAstrBot` is also available; a repository installation is a separate path and does not validate market installation.

## 2. Get a key with Suno access

New account? Register and sign in first. If the Applications page has no General application yet, choose **Initialize General Application**, then continue with the key steps below.

Sign in to [Ace Data Cloud Applications](https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=sunoastrbot_readme_api_key). Open **General application** to copy an existing key, or choose **Manage Keys → Create** for a separate AstrBot key. A service-specific key also works when it grants both `/suno/audios` and `/suno/tasks`. Check the current Suno price and your balance before generating.

Copy the key value only. Do not add `Bearer ` or use a `platform-...` management token. Do not put it in a chat message or repository file.

## 3. Configure AstrBot

Under **Extensions → Plugins → Installed**, select the gear icon on **Suno by Ace Data Cloud**. Paste the key into **Ace Data Cloud generation API key with Suno access** and save. AstrBot masks the field in WebUI, but its plugin configuration file stores the original value, so protect the AstrBot data directory.

Choose an active chat model that supports tool calling. In the current conversation's profile and persona, allow `suno_generate_music` and `suno_get_task`; see **Extensions → Handlers** if a tool is not available.

## 4. Generate once in chat

Send this request in AstrBot ChatUI or a connected messaging platform:

> Use `suno_generate_music` once to make a short instrumental piano melody for sunrise. Set `model` to `chirp-v6`, `duration` to `10`, and `instrumental` to true. Show me the returned task ID.

The tool returns `status: submitted` and a `task_id`. Keep that ID. `duration` is a target; the final track may be longer or shorter. The plugin never changes models automatically and never repeats a submission after a network error.

## 5. Query the same task

Ask the bot:

> Use `suno_get_task` with task ID `<the exact task_id>` and tell me its status. Do not generate another song.

If it returns `pending`, wait and query the **same ID** again. Preview audio may appear while the job runs; the plugin withholds it. Only `status: succeeded` and `success: true` indicate a finished job. Open one of the returned `audio_urls` to listen to the result. If the bot tries to submit a new job, stop it and request only `suno_get_task`.

## 6. Check billing and solve common failures

Open your Ace Data Cloud application usage or billing history and match the task or trace ID. A successful music generation should have its own usage record; task queries retrieve the existing job. Check the current price on the service page rather than assuming a fixed credit or USD amount.

| Symptom | Check |
| --- | --- |
| Plugin fails to load | AstrBot version, **Failed to Load Plugins**, then **Data & Logs → Logs**. |
| Tools do not appear | The plugin is enabled; the active profile and persona permit its tools; the chat model supports tool calling. |
| HTTP 401 or 403 | The key is a generation API key with Suno access, and any Allowed APIs restriction includes both paths. |
| Network error after submission | Inspect Ace request history before retrying generation; a timed-out response may still have created a job. |
| Pending task | Query the same task ID later. Do not repeat `suno_generate_music`. |
| Failed task | Use its task or trace ID in the service request history. Check any content policy or service error there. |

The plugin sends the key only to `https://api.acedata.cloud`, makes no automatic paid retries, and exposes only task status and final audio URLs to the model. It uses Python's standard library and needs no extra package.

## Verified local run

On AstrBot `v4.28.2`, an isolated editable installation registered both tools. A ChatUI conversation invoked each tool, submitted one `chirp-v6` generation, and retrieved the same task to `succeeded`. Two final MP3 files decoded as 18.024-second audio. One matching Suno API usage row reported 0.56 Credits before the account discount and 0.504 Credits deducted. The [sanitized evidence](tests/e2e-results.json) records the task and trace IDs.

## Verified market installation

On 2026-10-12, the public [Cloud listing](https://cloud.astrbot.app/plugin/AceDataCloud/astrbot_plugin_suno_acedatacloud) reported version `0.1.0`. A separate clean AstrBot `v4.28.2` instance installed the package through the official market and read back `install_method: market` and `activated: true`. ChatUI called `suno_get_task` once on the existing completed task and returned two final audio URLs, without another generation. [Sanitized market evidence](https://github.com/AceDataCloud/Index/blob/main/plans/ecosystem-growth/agent-provider-onboarding/execution/evidence/astrbot-market-20261012.json) records the installation and call.

## Brand asset

`logo.png` is a PNG encoding of the current [Suno service icon](https://cdn.acedata.cloud/l3ffw7.jpg), not a redrawn logo. The source JPEG is SHA-256 `d2ccb1c0039519a68913ad447114f8f9ecca161ffc2105cd61c414e06f8747d9`; the packaged PNG is SHA-256 `60794402c519a7d34bb50158d4442d0fbba814e3754a981bb5649468a1c8afc0`.
