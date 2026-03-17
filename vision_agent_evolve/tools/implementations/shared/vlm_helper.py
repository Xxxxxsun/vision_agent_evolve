"""Shared VLM helper utilities."""

from __future__ import annotations
import os
from pathlib import Path
from core.vlm_client import VLMClient, ModelSettings


def create_vlm_client(
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> VLMClient:
    """Create VLM client with env defaults."""
    return VLMClient(
        base_url=base_url or os.getenv("VLM_BASE_URL", "http://localhost:8000/v1"),
        api_key=api_key or os.getenv("VLM_API_KEY", "EMPTY"),
        model=model or os.getenv("VLM_MODEL", "gpt-4o"),
    )


def ask_vlm(
    client: VLMClient,
    image_path: str | Path,
    question: str,
    system_prompt: str = "You are a helpful vision assistant.",
) -> str:
    """Ask VLM a question about an image."""
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": VLMClient.image_message_parts(str(image_path), question),
        },
    ]

    return client.chat(messages, ModelSettings(temperature=0.1, max_tokens=500))
