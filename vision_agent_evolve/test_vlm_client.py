from __future__ import annotations

import json
import os
import tempfile
import base64
from urllib import error
import unittest
from unittest import mock

from PIL import Image

from core.vlm_client import VLMClient


class FakeHTTPResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class VLMClientAlibabaTests(unittest.TestCase):
    def test_image_data_url_compresses_large_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "large.png")
            noise = os.urandom(1800 * 1800 * 3)
            image = Image.frombytes("RGB", (1800, 1800), noise)
            image.save(image_path, format="PNG")

            data_url = VLMClient.image_data_url(image_path, max_bytes=400_000)

        self.assertTrue(data_url.startswith("data:image/jpeg;base64,"))
        encoded = data_url.split(",", 1)[1]
        decoded = base64.b64decode(encoded)
        self.assertLessEqual(len(decoded), 400_000)

    def test_openai_env_fallback_without_vlm_vars(self):
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
                "OPENAI_MODEL": "gpt-4o-mini",
                "VLM_API_KEY": "",
                "VLM_BASE_URL": "",
                "VLM_MODEL": "",
                "VLM_API_STYLE": "",
            },
            clear=False,
        ):
            client = VLMClient()

        self.assertEqual(client.base_url, "https://api.openai.com/v1")
        self.assertEqual(client.api_key, "openai-key")
        self.assertEqual(client.model, "gpt-4o-mini")
        self.assertEqual(client.api_style, "openai")

    def test_alibaba_chat_api_uses_prompt_string_for_single_text_message(self):
        with mock.patch.dict(
            os.environ,
            {
                "VLM_API_STYLE": "alibaba_chat",
                "VLM_API_KEY": "token-123",
                "VLM_MODEL": "gpt-5.4-0305-global",
                "VLM_USER_ID": "user-a",
                "VLM_ACCESS_KEY": "ak-1",
                "VLM_QUOTA_ID": "quota-9",
                "VLM_APP": "llm_application",
            },
            clear=False,
        ):
            client = VLMClient(base_url="https://llm-chat-api.alibaba-inc.com/v1/api/chat")

            with mock.patch("core.vlm_client.request.urlopen") as urlopen_mock:
                urlopen_mock.return_value = FakeHTTPResponse({"data": {"message": "hello"}})
                reply, usage = client.chat([{"role": "user", "content": "hi there"}])

            self.assertEqual(reply, "hello")
            self.assertEqual(usage.total_tokens, 0)
            request_obj = urlopen_mock.call_args.args[0]
            payload = json.loads(request_obj.data.decode("utf-8"))
            self.assertEqual(payload["prompt"], "hi there")
            self.assertEqual(payload["user_id"], "user-a")
            self.assertEqual(request_obj.headers["Authorization"], "token-123")

    def test_alibaba_chat_api_preserves_multimodal_prompt_array(self):
        with mock.patch.dict(
            os.environ,
            {
                "VLM_API_STYLE": "alibaba_chat",
                "VLM_API_KEY": "token-123",
                "VLM_MODEL": "gpt-5.4-0305-global",
                "VLM_USER_ID": "user-a",
                "VLM_ACCESS_KEY": "ak-1",
                "VLM_QUOTA_ID": "quota-9",
            },
            clear=False,
        ):
            client = VLMClient(base_url="https://llm-chat-api.alibaba-inc.com/v1/api/chat")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "what is in this chart?"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                    ],
                }
            ]

            with mock.patch("core.vlm_client.request.urlopen") as urlopen_mock:
                urlopen_mock.return_value = FakeHTTPResponse(
                    {
                        "data": {
                            "message": "bar chart",
                            "usage": {
                                "prompt_tokens": 10,
                                "completion_tokens": 4,
                                "total_tokens": 14,
                            },
                        }
                    }
                )
                reply, usage = client.chat(messages)

            self.assertEqual(reply, "bar chart")
            self.assertEqual(usage.total_tokens, 14)
            request_obj = urlopen_mock.call_args.args[0]
            payload = json.loads(request_obj.data.decode("utf-8"))
            self.assertEqual(payload["prompt"], messages)

    def test_alibaba_chat_retries_remote_disconnect_once(self):
        with mock.patch.dict(
            os.environ,
            {
                "VLM_API_STYLE": "alibaba_chat",
                "VLM_API_KEY": "token-123",
                "VLM_MODEL": "gpt-5.4-0305-global",
                "VLM_USER_ID": "user-a",
                "VLM_ACCESS_KEY": "ak-1",
                "VLM_QUOTA_ID": "quota-9",
            },
            clear=False,
        ):
            client = VLMClient(base_url="https://llm-chat-api.alibaba-inc.com/v1/api/chat")
            with mock.patch("core.vlm_client.request.urlopen") as urlopen_mock:
                urlopen_mock.side_effect = [
                    error.URLError("Remote end closed connection without response"),
                    FakeHTTPResponse({"data": {"message": "retry ok"}}),
                ]
                with mock.patch("core.vlm_client.time.sleep") as sleep_mock:
                    reply, _ = client.chat([{"role": "user", "content": "hi"}])

            self.assertEqual(reply, "retry ok")
            self.assertEqual(urlopen_mock.call_count, 2)
            sleep_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
