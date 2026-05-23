"""LLM 调用服务 — 纯 HTTP API（兼容 OpenAI 格式）

彻底移除 Hermes Agent / 子进程依赖，全部走 API 直连。
支持：DeepSeek、OpenAI、OpenRouter、Ollama 等任意兼容 OpenAI 的提供商。

配置方式（优先级：环境变量 > .env > 默认值）：
  LLM_API_KEY=sk-xxx
  LLM_BASE_URL=https://api.deepseek.com
  LLM_MODEL=deepseek-v4-flash
"""

import json
import logging
import os
import re
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ── 内部核心调用 ──


def _get_api_key() -> str:
    """获取 API Key：环境变量 > settings"""
    key = os.environ.get("LLM_API_KEY", "")
    if key:
        return key
    return settings.llm_api_key


def _llm_chat(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 8192,
    timeout: int = 180,
) -> str:
    """核心 LLM 调用 — 兼容 OpenAI 格式的 HTTP API"""
    api_key = _get_api_key()
    if not api_key:
        logger.error("❌ LLM_API_KEY 未设置！请通过 .env 或环境变量配置")
        raise ValueError("LLM_API_KEY 未设置，请在 .env 中配置")

    base_url = os.environ.get("LLM_BASE_URL", settings.llm_base_url).rstrip("/")
    model = os.environ.get("LLM_MODEL", settings.llm_model)

    # 兼容 DeepSeek 旧版 base_url（末尾带 /v1）
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    url = f"{base_url}/chat/completions"

    try:
        resp = httpx.post(
            url,
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        logger.info(f"✅ LLM API 调用成功，输出 {len(text)} 字符 (model={model})")
        return text
    except httpx.TimeoutException:
        logger.warning(f"⏱ LLM API 超时 ({timeout}s)")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ LLM API HTTP 错误 {e.response.status_code}: {e.response.text[:300]}")
        raise
    except Exception as e:
        logger.error(f"❌ LLM API 调用失败: {e}")
        raise


# ── 公开接口（保持签名不变，上层调用无需改动） ──


def call_llm_plain(
    prompt: str, timeout: int = 180, system_prompt: str | None = None
) -> str:
    """调用 LLM，返回原始文本（无 Hermes 人格包装，纯净输出）"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return _llm_chat(messages, timeout=timeout)


def call_llm(
    prompt: str, timeout: int | None = None, system_prompt: str | None = None
) -> str:
    """兼容旧接口：等同 call_llm_plain（原来走 Hermes，现在走 API）"""
    return call_llm_plain(prompt, timeout=timeout or 180, system_prompt=system_prompt)


def extract_json(text: str) -> dict | None:
    """从 LLM 输出中提取 JSON（支持多种格式混乱场景）"""
    if not text:
        return None

    # 1. 去掉行首的 diff 标记（+、-、┊ 等）
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("+") or stripped.startswith("-"):
            stripped = stripped[1:].strip()
        if stripped.startswith("┊"):
            stripped = stripped[1:].strip()
        cleaned_lines.append(stripped)
    cleaned = "\n".join(cleaned_lines)

    # 2. 尝试整体解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. 去掉 markdown 代码块标记
    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)

    # 4. 正则提取第一对 {}
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def call_llm_json(
    prompt: str,
    timeout: int | None = None,
    system_prompt: str | None = None,
    retry: bool = True,
) -> dict:
    """调用 LLM 并返回 JSON，失败时可选重试"""
    output = call_llm_plain(prompt, timeout=timeout or 180, system_prompt=system_prompt)
    result = extract_json(output)
    if result:
        return result
    if retry:
        retry_prompt = f"请只返回一个有效的 JSON 对象，不要任何其他文字。\n\n{prompt}"
        output = call_llm_plain(
            retry_prompt, timeout=timeout or 180, system_prompt=system_prompt
        )
        result = extract_json(output)
        if result:
            return result
    return {}
