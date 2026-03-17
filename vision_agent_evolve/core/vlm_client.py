"""VLM client for OpenAI-compatible APIs and Alibaba internal chat API."""

from __future__ import annotations
import os
import base64
import json
from urllib import request, error
from pathlib import Path
from typing import Any
from dataclasses import dataclass

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
        self.client = None if self.api_style == "alibaba_chat" else OpenAI(base_url=self.base_url, api_key=self.api_key)

    def chat(
        self,
        messages: list[dict[str, Any]],
        settings: ModelSettings | None = None,
    ) -> tuple[str, UsageStats]:
        """Send chat request and return response text with usage stats."""
        settings = settings or ModelSettings()
        if self.api_style == "alibaba_chat":
            return self._chat_alibaba(messages, settings)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout,
        )

        # Extract usage stats
        usage = UsageStats()
        if hasattr(response, 'usage') and response.usage:
            usage.prompt_tokens = getattr(response.usage, 'prompt_tokens', 0)
            usage.completion_tokens = getattr(response.usage, 'completion_tokens', 0)
            usage.total_tokens = getattr(response.usage, 'total_tokens', 0)

        content = response.choices[0].message.content or ""
        return content, usage

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
    def _infer_api_style(base_url: str) -> str:
        normalized = base_url.strip().lower()
        if "llm-chat-api.alibaba-inc.com" in normalized and normalized.endswith("/v1/api/chat"):
            return "alibaba_chat"
        return "openai"

    @staticmethod
    def _serialize_prompt(messages: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        """Map internal chat messages to the Alibaba prompt format."""
        if (
            len(messages) == 1
            and messages[0].get("role") == "user"
            and isinstance(messages[0].get("content"), str)
        ):
            return str(messages[0]["content"])
        return messages

    @staticmethod
    def image_message_parts(image_path: str, text: str) -> list[dict[str, Any]]:
        """Create message content with image attachment."""
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Read and encode image
        with open(image_path_obj, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Detect mime type
        suffix = image_path_obj.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(suffix, "image/png")

        return [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
            },
        ]
