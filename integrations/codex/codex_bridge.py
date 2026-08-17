"""OpenAI-compatible Codex OAuth bridge for waoowaoo.

``codex-as-api`` supplies the Codex/ChatGPT OAuth transport.  This compatibility
layer adds the model catalog expected by waoowaoo, supplies minimal system
instructions for connection probes, and normalizes generated images to both a
data URL and ``b64_json``.

The bridge never reads or logs token values itself. Authentication remains
owned by Codex and the pinned ``codex-as-api`` dependency.
"""

from __future__ import annotations

import json
import os
from typing import Any

import uvicorn
from codex_as_api.server import app
from fastapi import Request
from fastapi.responses import JSONResponse, Response


TEXT_MODELS = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5")


@app.get("/v1/models")
async def list_models() -> JSONResponse:
    models = [
        {"id": model_id, "object": "model", "owned_by": "codex-oauth"}
        for model_id in TEXT_MODELS
    ]
    return JSONResponse({"object": "list", "data": models})


def _response_headers(response: Response) -> dict[str, str]:
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() != "content-length"
    }


def _normalize_image_response(payload: dict[str, Any]) -> bool:
    changed = False
    data = payload.get("data")
    if not isinstance(data, list):
        return changed

    for item in data:
        if not isinstance(item, dict):
            continue
        raw_url = item.get("url")
        if not isinstance(raw_url, str) or not raw_url:
            continue
        if raw_url.startswith(("http://", "https://", "data:image/")):
            continue
        item["b64_json"] = raw_url
        item["url"] = f"data:image/png;base64,{raw_url}"
        changed = True
    return changed


@app.middleware("http")
async def normalize_waoowaoo_compatibility(request: Request, call_next):
    response = await call_next(request)
    if request.url.path != "/v1/images/generations" or response.status_code >= 400:
        return response

    body = b"".join([chunk async for chunk in response.body_iterator])
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        payload = None

    if not isinstance(payload, dict) or not _normalize_image_response(payload):
        return Response(
            content=body,
            status_code=response.status_code,
            headers=_response_headers(response),
            media_type=response.media_type,
        )

    return JSONResponse(
        payload,
        status_code=response.status_code,
        headers=_response_headers(response),
    )


class EnsureSystemInstructionsMiddleware:
    """Add instructions when a connection probe only supplies user content."""

    def __init__(self, inner_app):
        self.inner_app = inner_app

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/v1/chat/completions"
        ):
            await self.inner_app(scope, receive, send)
            return

        chunks: list[bytes] = []
        more_body = True
        while more_body:
            message = await receive()
            chunks.append(message.get("body", b""))
            more_body = bool(message.get("more_body", False))
        body = b"".join(chunks)

        try:
            payload = json.loads(body)
        except (TypeError, ValueError):
            payload = None

        if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            messages = payload["messages"]
            has_instructions = any(
                isinstance(item, dict)
                and item.get("role") in {"system", "developer"}
                for item in messages
            )
            if not has_instructions:
                messages.insert(
                    0,
                    {"role": "system", "content": "You are a helpful assistant."},
                )
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                headers = [
                    (key, value)
                    for key, value in scope.get("headers", [])
                    if key.lower() != b"content-length"
                ]
                headers.append((b"content-length", str(len(body)).encode("ascii")))
                scope = {**scope, "headers": headers}

        sent = False

        async def replay_receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.inner_app(scope, replay_receive, send)


app.add_middleware(EnsureSystemInstructionsMiddleware)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("CODEX_AS_API_HOST", "127.0.0.1"),
        port=int(os.getenv("CODEX_AS_API_PORT", "18080")),
        log_level=os.getenv("CODEX_AS_API_LOG_LEVEL", "info"),
    )
