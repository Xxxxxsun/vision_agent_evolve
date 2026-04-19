"""VLM client for OpenAI-compatible APIs, Anthropic Messages, and Alibaba chat."""

from __future__ import annotations
import os
import base64
import http.client
import json
import socket
import time
from urllib import request, error
from pathlib import Path
from typing import Any
from dataclasses import dataclass

from PIL import Image

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("Please install openai: pip install openai")


@dataclass
class ModelSettings:
    """LLM generation settings."""
    temperature: float = 0.2
    max_tokens: int = 1400
    timeout: int = 120
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0


@dataclass
class UsageStats:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other):
        """Add two usage stats together."""
        return UsageStats(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class VLMClient:
    """VLM client with support for OpenAI-compatible and Alibaba internal chat APIs."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        default_base_url = "https://api.openai.com/v1" if openai_api_key else "http://localhost:8000/v1"
        self.base_url = (
            base_url
            or os.getenv("VLM_BASE_URL", "").strip()
            or os.getenv("OPENAI_BASE_URL", "").strip()
            or default_base_url
        )
        self.api_key = api_key or os.getenv("VLM_API_KEY", "").strip() or openai_api_key or "EMPTY"
        self.model = (
            model
            or os.getenv("VLM_MODEL", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
            or "gpt-4o"
        )
        self.api_style = os.getenv("VLM_API_STYLE", "").strip().lower() or self._infer_api_style(self.base_url)
        self.user_id = os.getenv("VLM_USER_ID", "").strip()
        self.access_key = os.getenv("VLM_ACCESS_KEY", "").strip()
        self.quota_id = os.getenv("VLM_QUOTA_ID", "").strip()
        self.app = os.getenv("VLM_APP", "").strip() or "llm_application"
        self.client = None if self.api_style in {"alibaba_chat", "responses", "anthropic_messages"} else OpenAI(base_url=self.base_url, api_key=self.api_key)

    def chat(
        self,
        messages: list[dict[str, Any]],
        settings: ModelSettings | None = None,
    ) -> tuple[str, UsageStats]:
        """Send chat request and return response text with usage stats."""
        settings = settings or ModelSettings()
        attempts = max(1, settings.max_retries)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                if self.api_style == "alibaba_chat":
                    return self._chat_alibaba(messages, settings)
                if self.api_style == "responses":
                    return self._chat_responses(messages, settings)
                if self.api_style == "anthropic_messages":
                    return self._chat_anthropic_messages(messages, settings)

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=settings.temperature,
                    max_tokens=settings.max_tokens,
                    timeout=settings.timeout,
                )

                usage = UsageStats()
                if hasattr(response, "usage") and response.usage:
                    usage.prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
                    usage.completion_tokens = getattr(response.usage, "completion_tokens", 0)
                    usage.total_tokens = getattr(response.usage, "total_tokens", 0)

                content = response.choices[0].message.content or ""
                return content, usage
            except Exception as exc:  # pragma: no cover - retry path depends on backend behavior
                last_error = exc
                if attempt >= attempts or not self._is_retryable_exception(exc):
                    raise
                delay = settings.retry_backoff_seconds * attempt
                print(
                    f"[VLMClient] transient error on attempt {attempt}/{attempts}: {exc}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

        assert last_error is not None
        raise last_error

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        settings: ModelSettings | None = None,
        raw_response: bool = False,
    ) -> tuple[Any, UsageStats]:
        """Send a tool-calling chat request and optionally return the raw response object."""
        settings = settings or ModelSettings()

        attempts = max(1, settings.max_retries)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                if self.api_style == "alibaba_chat":
                    return self._chat_alibaba_with_tools(messages, tools, settings, raw_response=raw_response)
                if self.api_style == "responses":
                    return self._chat_responses_with_tools(messages, tools, settings, raw_response=raw_response)
                if self.api_style == "anthropic_messages":
                    return self._chat_anthropic_messages_with_tools(messages, tools, settings, raw_response=raw_response)

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=settings.temperature,
                    max_tokens=settings.max_tokens,
                    timeout=settings.timeout,
                    tools=tools,
                )

                usage = UsageStats()
                if hasattr(response, "usage") and response.usage:
                    usage.prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
                    usage.completion_tokens = getattr(response.usage, "completion_tokens", 0)
                    usage.total_tokens = getattr(response.usage, "total_tokens", 0)

                if raw_response:
                    return response, usage

                content = response.choices[0].message.content or ""
                return content, usage
            except Exception as exc:  # pragma: no cover - retry path depends on backend behavior
                last_error = exc
                if attempt >= attempts or not self._is_retryable_exception(exc):
                    raise
                delay = settings.retry_backoff_seconds * attempt
                print(
                    f"[VLMClient] transient tool-calling error on attempt {attempt}/{attempts}: {exc}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

        assert last_error is not None
        raise last_error

    def _chat_alibaba_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        settings: ModelSettings,
        *,
        raw_response: bool = False,
    ) -> tuple[Any, UsageStats]:
        """Send a tool-calling request to the Alibaba internal chat API."""
        self._validate_alibaba_config()
        payload = {
            "model": self.model,
            "prompt": self._serialize_prompt(messages),
            "user_id": self.user_id,
            "access_key": self.access_key,
            "quota_id": self.quota_id,
            "app": self.app,
            "params": {
                "temperature": settings.temperature,
                "max_tokens": settings.max_tokens,
            },
        }
        if tools:
            payload["params"]["tools"] = tools
        if self._is_gemini_model():
            payload["params"].update(self._gemini_params(settings))
            payload["tag"] = os.getenv("VLM_TAG", "").strip() or "web_chat_client"
            payload["category"] = os.getenv("VLM_CATEGORY", "").strip() or "问答"

        req = request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.timeout) as resp:
                response_body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Alibaba chat API HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Alibaba chat API request failed: {exc}") from exc

        parsed = json.loads(response_body)
        usage = UsageStats()
        data = parsed.get("data") if isinstance(parsed, dict) else None
        completion = data.get("completion") if isinstance(data, dict) else None
        usage_payload = None
        if isinstance(completion, dict):
            usage_payload = completion.get("usage")
        if not isinstance(usage_payload, dict) and isinstance(data, dict):
            usage_payload = data.get("usage")
        if isinstance(usage_payload, dict):
            usage.prompt_tokens = int(usage_payload.get("prompt_tokens", 0) or 0)
            usage.completion_tokens = int(usage_payload.get("completion_tokens", 0) or 0)
            usage.total_tokens = int(
                usage_payload.get("total_tokens", usage.prompt_tokens + usage.completion_tokens) or 0
            )

        if raw_response:
            return parsed, usage

        message = ""
        if isinstance(data, dict):
            message = str(data.get("message", "") or "")
        return message, usage

    def _chat_responses_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        settings: ModelSettings,
        *,
        raw_response: bool = False,
    ) -> tuple[Any, UsageStats]:
        """Send a request to an OpenAI Responses-style endpoint."""
        payload: dict[str, Any] = {
            "input": self._serialize_responses_input(messages),
            "stream": False,
            "model": self.model,
            "temperature": settings.temperature,
            "max_output_tokens": settings.max_tokens,
        }
        if tools:
            payload["tools"] = tools

        req = request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.timeout) as resp:
                response_body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Responses API HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Responses API request failed: {exc}") from exc

        parsed = json.loads(response_body)
        usage = UsageStats()
        usage_payload = parsed.get("usage") if isinstance(parsed, dict) else None
        if isinstance(usage_payload, dict):
            usage.prompt_tokens = int(usage_payload.get("input_tokens", 0) or 0)
            usage.completion_tokens = int(usage_payload.get("output_tokens", 0) or 0)
            usage.total_tokens = int(usage_payload.get("total_tokens", usage.prompt_tokens + usage.completion_tokens) or 0)

        message = self._extract_responses_text(parsed)
        if raw_response:
            return {
                "data": {
                    "message": message,
                    "completion": {
                        "choices": [
                            {
                                "message": {
                                    "content": message,
                                }
                            }
                        ]
                    },
                },
                "responses": parsed,
            }, usage
        return message, usage

    def _chat_responses(
        self,
        messages: list[dict[str, Any]],
        settings: ModelSettings,
    ) -> tuple[str, UsageStats]:
        response, usage = self._chat_responses_with_tools(messages, tools=None, settings=settings, raw_response=False)
        return str(response), usage

    def _chat_anthropic_messages_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        settings: ModelSettings,
        *,
        raw_response: bool = False,
    ) -> tuple[Any, UsageStats]:
        """Send a request to an Anthropic Messages-style endpoint."""
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": settings.max_tokens,
            "messages": self._serialize_anthropic_messages(messages),
        }
        system_prompt = self._extract_anthropic_system(messages)
        if system_prompt:
            payload["system"] = system_prompt
        if settings.temperature is not None:
            payload["temperature"] = settings.temperature
        if tools:
            payload["tools"] = tools

        req = request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "anthropic-version": os.getenv("VLM_ANTHROPIC_VERSION", "2023-06-01"),
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.timeout) as resp:
                response_body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic Messages API HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Anthropic Messages API request failed: {exc}") from exc

        parsed = json.loads(response_body)
        usage = UsageStats()
        usage_payload = parsed.get("usage") if isinstance(parsed, dict) else None
        if isinstance(usage_payload, dict):
            usage.prompt_tokens = int(usage_payload.get("input_tokens", 0) or 0)
            usage.completion_tokens = int(usage_payload.get("output_tokens", 0) or 0)
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

        message = self._extract_anthropic_text(parsed)
        if raw_response:
            return {
                "data": {
                    "message": message,
                    "completion": {
                        "choices": [
                            {
                                "message": {
                                    "content": message,
                                }
                            }
                        ]
                    },
                },
                "anthropic": parsed,
            }, usage
        return message, usage

    def _chat_anthropic_messages(
        self,
        messages: list[dict[str, Any]],
        settings: ModelSettings,
    ) -> tuple[str, UsageStats]:
        response, usage = self._chat_anthropic_messages_with_tools(
            messages,
            tools=None,
            settings=settings,
            raw_response=False,
        )
        return str(response), usage

    def _chat_alibaba(
        self,
        messages: list[dict[str, Any]],
        settings: ModelSettings,
    ) -> tuple[str, UsageStats]:
        """Send a request to the Alibaba internal chat API."""
        self._validate_alibaba_config()
        payload = {
            "model": self.model,
            "prompt": self._serialize_prompt(messages),
            "user_id": self.user_id,
            "access_key": self.access_key,
            "quota_id": self.quota_id,
            "app": self.app,
        }
        if self._is_gemini_model():
            payload["params"] = self._gemini_params(settings)
            payload["tag"] = os.getenv("VLM_TAG", "").strip() or "web_chat_client"
            payload["category"] = os.getenv("VLM_CATEGORY", "").strip() or "问答"

        req = request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.timeout) as resp:
                response_body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Alibaba chat API HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Alibaba chat API request failed: {exc}") from exc

        parsed = json.loads(response_body)
        data = parsed.get("data") if isinstance(parsed, dict) else {}
        message = ""
        if isinstance(data, dict):
            message = str(data.get("message", "") or "")
        if not message and isinstance(parsed, dict):
            message = str(parsed.get("message", "") or "")

        usage = UsageStats()
        usage_payload = data.get("usage") if isinstance(data, dict) else None
        if not isinstance(usage_payload, dict) and isinstance(parsed, dict):
            usage_payload = parsed.get("usage")
        if isinstance(usage_payload, dict):
            usage.prompt_tokens = int(usage_payload.get("prompt_tokens", 0) or 0)
            usage.completion_tokens = int(usage_payload.get("completion_tokens", 0) or 0)
            usage.total_tokens = int(
                usage_payload.get("total_tokens", usage.prompt_tokens + usage.completion_tokens) or 0
            )

        return message, usage

    def _validate_alibaba_config(self) -> None:
        missing = []
        if not self.api_key:
            missing.append("VLM_API_KEY")
        if not self.user_id:
            missing.append("VLM_USER_ID")
        if not self.access_key:
            missing.append("VLM_ACCESS_KEY")
        if not self.quota_id:
            missing.append("VLM_QUOTA_ID")
        if missing:
            raise ValueError(
                "Alibaba chat API requires the following env vars: " + ", ".join(missing)
            )

    @staticmethod
    def _is_retryable_exception(exc: Exception) -> bool:
        """Best-effort filter for transient transport failures."""
        if isinstance(exc, (TimeoutError, socket.timeout, ConnectionResetError, http.client.RemoteDisconnected)):
            return True
        if isinstance(exc, error.URLError):
            return True

        text = str(exc).lower()
        transient_markers = [
            "remote end closed connection without response",
            "timed out",
            "timeout",
            "connection reset",
            "temporarily unavailable",
            "server disconnected",
            "connection aborted",
            "connection refused",
            "transport",
        ]
        return any(marker in text for marker in transient_markers)

    @staticmethod
    def _infer_api_style(base_url: str) -> str:
        normalized = base_url.strip().lower()
        if "llm-chat-api.alibaba-inc.com" in normalized and normalized.endswith("/v1/api/chat"):
            return "alibaba_chat"
        if normalized.endswith("/v1/responses") or "/protocol/openai/v1/responses" in normalized:
            return "responses"
        if normalized.endswith("/v1/messages") or "/protocol/anthropic/v1/messages" in normalized:
            return "anthropic_messages"
        return "openai"

    def _serialize_prompt(self, messages: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        """Map internal chat messages to the backend-specific prompt format."""
        if self._is_gemini_model():
            return self._serialize_prompt_gemini(messages)
        if (
            len(messages) == 1
            and messages[0].get("role") == "user"
            and isinstance(messages[0].get("content"), str)
        ):
            return str(messages[0]["content"])
        return messages

    def _serialize_responses_input(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map internal chat messages to OpenAI Responses input format."""
        serialized: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user")).strip().lower() or "user"
            content = message.get("content", "")
            if isinstance(content, str):
                serialized.append({"role": role, "content": content})
                continue
            if not isinstance(content, list):
                serialized.append({"role": role, "content": str(content)})
                continue

            parts: list[dict[str, Any]] = []
            for item in content:
                if not isinstance(item, dict):
                    parts.append({"type": "input_text", "text": str(item)})
                    continue
                item_type = str(item.get("type", "")).strip().lower()
                if item_type == "text":
                    parts.append({"type": "input_text", "text": str(item.get("text", ""))})
                    continue
                if item_type == "image_url":
                    image_url = item.get("image_url") or {}
                    url = str(image_url.get("url", ""))
                    if url:
                        parts.append({"type": "input_image", "image_url": url})
                    continue
                parts.append({"type": "input_text", "text": str(item)})
            serialized.append({"role": role, "content": parts})
        return serialized

    def _serialize_anthropic_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map internal chat messages to Anthropic Messages format."""
        serialized: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user")).strip().lower() or "user"
            if role == "system":
                continue
            normalized_role = "assistant" if role == "assistant" else "user"
            content = message.get("content", "")
            if isinstance(content, str):
                serialized.append({"role": normalized_role, "content": content})
                continue
            if not isinstance(content, list):
                serialized.append({"role": normalized_role, "content": str(content)})
                continue

            parts: list[dict[str, Any]] = []
            for item in content:
                if not isinstance(item, dict):
                    parts.append({"type": "text", "text": str(item)})
                    continue
                item_type = str(item.get("type", "")).strip().lower()
                if item_type == "text":
                    parts.append({"type": "text", "text": str(item.get("text", ""))})
                    continue
                if item_type == "image_url":
                    image_url = item.get("image_url") or {}
                    url = str(image_url.get("url", ""))
                    if not url:
                        continue
                    if url.startswith("data:"):
                        header, encoded = url.split(",", 1)
                        media_type = header.split(":", 1)[1].split(";", 1)[0]
                        parts.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": encoded,
                                },
                            }
                        )
                    else:
                        parts.append({"type": "image", "source": {"type": "url", "url": url}})
                    continue
                parts.append({"type": "text", "text": str(item)})
            serialized.append({"role": normalized_role, "content": parts or [{"type": "text", "text": ""}]})
        return serialized

    @staticmethod
    def _extract_anthropic_system(messages: list[dict[str, Any]]) -> str | None:
        texts: list[str] = []
        for message in messages:
            if str(message.get("role", "")).strip().lower() != "system":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and str(item.get("type", "")).strip().lower() == "text":
                        texts.append(str(item.get("text", "")))
                    else:
                        texts.append(str(item))
            else:
                texts.append(str(content))
        joined = "\n".join(part.strip() for part in texts if str(part).strip()).strip()
        return joined or None

    @staticmethod
    def _extract_anthropic_text(parsed: dict[str, Any]) -> str:
        content = parsed.get("content") if isinstance(parsed, dict) else None
        if not isinstance(content, list):
            return ""
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text", "")))
        return "".join(texts).strip()

    @staticmethod
    def _extract_responses_text(parsed: dict[str, Any]) -> str:
        output = parsed.get("output") if isinstance(parsed, dict) else None
        if not isinstance(output, list):
            return ""
        texts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("role") != "assistant":
                continue
            contents = item.get("content")
            if not isinstance(contents, list):
                continue
            for content in contents:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    texts.append(str(content.get("text", "")))
        return "".join(texts).strip()

    def _is_gemini_model(self) -> bool:
        return self.api_style == "alibaba_chat" and "gemini" in self.model.strip().lower()

    def _gemini_params(self, settings: ModelSettings) -> dict[str, Any]:
        params: dict[str, Any] = {
            "use_gemini_httpstream_api": "1",
            "temperature": settings.temperature,
            "maxOutputTokens": settings.max_tokens,
            # Keep both spellings for proxy compatibility; docs and examples conflict.
            "max_tokens": settings.max_tokens,
            # Avoid returning thought traces to the caller.
            "includeThoughts": False,
            "thinkingBudget": max(256, settings.max_tokens // 2),
        }
        response_mime_type = os.getenv("VLM_GEMINI_RESPONSE_MIME_TYPE", "").strip()
        if response_mime_type:
            params["responseMimeType"] = response_mime_type
        return params

    def _serialize_prompt_gemini(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prompt: list[dict[str, Any]] = []
        system_texts: list[str] = []
        for message in messages:
            role = str(message.get("role", "user")).strip().lower() or "user"
            content = message.get("content", "")
            if role == "system":
                system_text = self._flatten_system_content(content)
                if system_text:
                    system_texts.append(system_text)
                continue

            parts = self._gemini_parts_from_content(content)
            if system_texts and role == "user":
                prefix = "\n\n".join(system_texts)
                parts = [{"text": f"System instruction:\n{prefix}"}] + parts
                system_texts = []
            prompt.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": parts or [{"text": ""}],
                }
            )
        if system_texts and not prompt:
            prompt.append({"role": "user", "parts": [{"text": "\n\n".join(system_texts)}]})
        return prompt

    def _gemini_parts_from_content(self, content: Any) -> list[dict[str, Any]]:
        if isinstance(content, str):
            return [{"text": content}]
        if not isinstance(content, list):
            return [{"text": str(content)}]

        parts: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append({"text": str(item)})
                continue
            item_type = str(item.get("type", "")).strip().lower()
            if item_type == "text":
                parts.append({"text": str(item.get("text", ""))})
                continue
            if item_type == "image_url":
                image_url = item.get("image_url") or {}
                url = str(image_url.get("url", ""))
                mime_type, data = self._gemini_inline_data(url)
                parts.append({"inlineData": {"mimeType": mime_type, "data": data}})
                continue
            parts.append({"text": str(item)})
        return parts

    @staticmethod
    def _flatten_system_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and str(item.get("type", "")).strip().lower() == "text":
                texts.append(str(item.get("text", "")))
            else:
                texts.append(str(item))
        return "\n".join(texts).strip()

    @staticmethod
    def _gemini_inline_data(url: str) -> tuple[str, str]:
        if url.startswith("data:"):
            header, encoded = url.split(",", 1)
            mime_type = header.split(":", 1)[1].split(";", 1)[0]
            return mime_type, encoded
        if url.startswith("http://") or url.startswith("https://"):
            return "image/png", url
        raise ValueError(f"Unsupported Gemini image payload: {url[:80]}")

    @staticmethod
    def image_message_parts(image_path: str, text: str) -> list[dict[str, Any]]:
        """Create message content with image attachment."""
        data_url = VLMClient.image_data_url(image_path)

        return [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": data_url},
            },
        ]

    @staticmethod
    def image_data_url(image_path: str | Path, max_bytes: int = 3_500_000) -> str:
        """Create a data URL, downscaling/compressing oversized images when needed."""
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        raw_bytes = image_path_obj.read_bytes()
        suffix = image_path_obj.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(suffix, "image/png")
        if len(raw_bytes) <= max_bytes and mime_type in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
            image_data = base64.b64encode(raw_bytes).decode("utf-8")
            return f"data:{mime_type};base64,{image_data}"

        optimized_bytes, optimized_mime = VLMClient._optimize_image_bytes(image_path_obj, max_bytes=max_bytes)
        image_data = base64.b64encode(optimized_bytes).decode("utf-8")
        return f"data:{optimized_mime};base64,{image_data}"

    @staticmethod
    def _optimize_image_bytes(image_path: Path, max_bytes: int = 3_500_000) -> tuple[bytes, str]:
        with Image.open(image_path) as image:
            working = image.convert("RGB") if image.mode not in {"RGB", "L"} else image.copy()

        max_dim = max(working.size)
        quality = 90
        while True:
            buffer = VLMClient._encode_jpeg(working, quality=quality)
            if len(buffer) <= max_bytes:
                return buffer, "image/jpeg"

            if max_dim <= 768 and quality <= 45:
                return buffer, "image/jpeg"

            if quality > 45:
                quality -= 10
                continue

            max_dim = max(768, int(max_dim * 0.8))
            working = VLMClient._resize_longest_edge(working, max_dim)
            quality = 85

    @staticmethod
    def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
        import io

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        return buffer.getvalue()

    @staticmethod
    def _resize_longest_edge(image: Image.Image, max_dim: int) -> Image.Image:
        width, height = image.size
        longest = max(width, height)
        if longest <= max_dim:
            return image.copy()
        scale = max_dim / float(longest)
        resized = image.copy()
        resized.thumbnail((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
        return resized
