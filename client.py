"""Minimal Ace Data Cloud Suno transport for AstrBot."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_BASE = "https://api.acedata.cloud"
MODELS = {"chirp-v6", "chirp-v6-mini", "chirp-v6-wild"}
COMPLETE = {"complete", "completed", "succeeded", "success", "finished"}
FAILED = {"failed", "error", "cancelled", "canceled", "rejected"}


class _NoRedirect(HTTPRedirectHandler):
    """Never forward an API key to a redirected host."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        """Reject every redirect from the fixed API host.

        Args:
            request: Original request.
            fp: Response stream.
            code: Redirect HTTP status.
            msg: HTTP status text.
            headers: Redirect headers.
            newurl: Redirect target.

        Returns:
            None so urllib raises instead of following the redirect.
        """
        return


OPENER = build_opener(_NoRedirect)


class SunoError(RuntimeError):
    """A safe error message for a user-facing AstrBot tool."""


class SunoClient:
    """Submit one Suno job or query an existing task ID."""

    def __init__(self, api_key: str) -> None:
        """Keep a service or global API key in memory only.

        Args:
            api_key: Ace Data Cloud generation API key without a Bearer prefix.

        Raises:
            SunoError: If the key is missing or is a platform management token.
        """
        token = api_key.strip()
        if (
            not token
            or token.lower().startswith("bearer ")
            or token.startswith("platform-")
        ):
            raise SunoError(
                "Set an Ace Data Cloud generation API key in plugin settings."
            )
        self._api_key = token

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one request; generation is never retried automatically.

        Args:
            path: Fixed Suno API path.
            payload: JSON request body.

        Returns:
            Parsed JSON response with a trace ID when the server supplied one.

        Raises:
            SunoError: For network, HTTP, or response-format failures.
        """
        request = Request(
            API_BASE + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "AceDataCloudAstrBot/0.1.1",
            },
            method="POST",
        )
        try:
            with OPENER.open(request, timeout=60) as response:
                body = json.load(response)
                trace_id = response.headers.get("x-trace-id", "")
        except HTTPError as exc:
            raise SunoError(
                f"Ace Data Cloud returned HTTP {exc.code}. Check service access and request history."
            ) from None
        except (URLError, TimeoutError, OSError):
            raise SunoError(
                "The API connection failed. Check request history before submitting again."
            ) from None
        except (ValueError, UnicodeError):
            raise SunoError(
                "The API returned invalid JSON. Check request history before retrying."
            ) from None
        if not isinstance(body, dict):
            raise SunoError("The API returned an unexpected response format.")
        if trace_id and not body.get("trace_id"):
            body["trace_id"] = trace_id
        return body

    async def submit(
        self,
        prompt: str,
        instrumental: bool = True,
        duration: int = 0,
        model: str = "chirp-v6",
    ) -> dict[str, Any]:
        """Submit one asynchronous music generation and return its task ID.

        Args:
            prompt: Original description of the desired song.
            instrumental: Whether to generate without vocals.
            duration: Optional target length in seconds; zero lets Suno choose.
            model: Explicit supported Suno model; there is no fallback.

        Returns:
            A submitted status, task ID, and optional trace ID.

        Raises:
            SunoError: If parameters or the submission response are invalid.
        """
        if not prompt.strip():
            raise SunoError("Describe the music to generate.")
        if model not in MODELS:
            raise SunoError("Choose chirp-v6, chirp-v6-mini, or chirp-v6-wild.")
        if duration and (not isinstance(duration, int) or not 10 <= duration <= 360):
            raise SunoError("Duration must be 10–360 seconds or omitted.")
        payload: dict[str, Any] = {
            "action": "generate",
            "prompt": prompt.strip(),
            "instrumental": instrumental,
            "model": model,
            "async": True,
        }
        if duration:
            payload["duration"] = duration
        body = await asyncio.to_thread(self._post, "/suno/audios", payload)
        if body.get("success") is False or body.get("error"):
            raise SunoError(
                "Generation was rejected. Check the request history before retrying."
            )
        task = body.get("task")
        task_id = body.get("task_id") or (
            task.get("id") if isinstance(task, dict) else None
        )
        if not isinstance(task_id, str) or not task_id:
            raise SunoError(
                "No task ID was returned. Check request history before submitting again."
            )
        return {
            "status": "submitted",
            "task_id": task_id,
            "trace_id": str(body.get("trace_id") or ""),
            "next_step": "Query this task ID; do not submit a second generation while it is pending.",
        }

    async def query(self, task_id: str) -> dict[str, Any]:
        """Retrieve a task without creating another generation.

        Args:
            task_id: ID returned by an earlier submission.

        Returns:
            Pending, failed, or terminal successful status and final audio URLs.

        Raises:
            SunoError: If the task ID or lookup response is invalid.
        """
        task_id = task_id.strip()
        if not task_id:
            raise SunoError("Pass the task ID returned by Suno generation.")
        body = await asyncio.to_thread(
            self._post, "/suno/tasks", {"action": "retrieve", "id": task_id}
        )
        response = body.get("response", body)
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except ValueError:
                response = {}
        if not isinstance(response, dict):
            response = {}
        if not response:
            return {
                "task_id": task_id,
                "trace_id": str(body.get("trace_id") or ""),
                "status": "pending",
                "success": False,
                "audio_urls": [],
            }
        state = str(response.get("state") or response.get("status") or "").lower()
        unfinished = "finished_at" in body and body["finished_at"] is None
        failed = (
            state in FAILED
            or response.get("success") is False
            or bool(response.get("error"))
        )
        result = {
            "task_id": task_id,
            "trace_id": str(response.get("trace_id") or body.get("trace_id") or ""),
        }
        if failed:
            return {**result, "status": "failed", "success": False, "audio_urls": []}
        if unfinished or (not state and not body.get("finished_at")):
            return {**result, "status": "pending", "success": False, "audio_urls": []}
        if state not in COMPLETE and not body.get("finished_at"):
            return {**result, "status": "pending", "success": False, "audio_urls": []}
        urls: list[str] = []

        def collect(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if (
                        key == "audio_url"
                        and isinstance(value, str)
                        and value.startswith("https://")
                    ):
                        urls.append(value)
                    elif isinstance(value, (dict, list)):
                        collect(value)
            elif isinstance(node, list):
                for item in node:
                    collect(item)

        collect(response)
        return {
            **result,
            "status": "succeeded",
            "success": True,
            "audio_urls": list(dict.fromkeys(urls)),
        }
