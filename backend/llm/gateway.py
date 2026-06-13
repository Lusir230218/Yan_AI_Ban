"""OpenAI 兼容的 LLM 异步调用网关"""

from __future__ import annotations

from typing import Any

import httpx

from config import settings


class LLMResponse:
    def __init__(self, text: str, **kwargs: Any) -> None:
        self.text = text
        self.extra = kwargs


async def llm_chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> LLMResponse:
    """调用 OpenAI 兼容的 Chat Completion API"""
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model or settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.LLM_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return LLMResponse(
        text=data["choices"][0]["message"]["content"],
        usage=data.get("usage"),
        model=data.get("model"),
    )
