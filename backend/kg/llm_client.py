"""LLM 调用封装 — Anthropic 兼容协议。

阶段五 LLM 与阶段一 OpenAI 协议分开，用 STAGE5_LLM_* 配置。
详见 memory/stage5-llm-choice.md。
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import anthropic

from config import settings


class LLMError(Exception):
    pass


_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    """单例 async client（懒加载）。"""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(
            auth_token=settings.STAGE5_LLM_API_KEY,
            base_url=settings.STAGE5_LLM_BASE_URL,
        )
    return _client


async def chat_json(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 4000,
    max_retries: int = 3,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """调 Anthropic 兼容 LLM 拿 JSON 返回。

    失败重试：网络错误 / JSON 解析失败。
    schema 校验失败由 extract.py._extract_one_chunk 处理（不在这里重试）。
    """
    client = _get_client()
    model = model or settings.STAGE5_LLM_MODEL

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                timeout=timeout,
            )
            text = resp.content[0].text
            return _strict_json_loads(text)
        except (anthropic.APIError, anthropic.APIConnectionError,
                anthropic.APITimeoutError, KeyError, ValueError) as e:
            last_err = e
            await asyncio.sleep(2 ** attempt)
    raise LLMError(f"LLM 调 {max_retries} 次失败: {last_err}")


def _strict_json_loads(s: str) -> dict[str, Any]:
    """剥离 markdown 围栏 + 注释，保证返回合法 JSON dict。"""
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise LLMError(f"JSON 解析失败: {e}\n原始: {s[:500]}")