"""OpenAI 兼容的 LLM 异步调用网关（文本 + 多模态 Vision）"""

from __future__ import annotations

import base64
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
    """调用 OpenAI 兼容的 Chat Completion API（纯文本）"""
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


async def llm_vision_chat(
    text_prompt: str,
    image_base64: str,
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> LLMResponse:
    """调用多模态 Vision 模型发送图片 + 文本提示"""
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model or settings.LLM_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ],
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
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
