# VTool-R1 API Environment Template

Use this template when running the no-GPU API comparison line.

## Alibaba Chat Proxy

```bash
export VLM_API_STYLE="alibaba_chat"
export VLM_BASE_URL="https://llm-chat-api.alibaba-inc.com/v1/api/chat"
export VLM_API_KEY="YOUR_PROXY_TOKEN"
export VLM_MODEL="YOUR_VISION_MODEL"
export VLM_USER_ID="YOUR_USER_ID"
export VLM_ACCESS_KEY="YOUR_ACCESS_KEY"
export VLM_QUOTA_ID="YOUR_QUOTA_ID"
```

Optional:

```bash
export VLM_APP="llm_application"
export VLM_CATEGORY="问答"
export VLM_GEMINI_RESPONSE_MIME_TYPE="text/plain"
```

## OpenAI-Compatible Proxy

```bash
export VLM_BASE_URL="https://your-proxy.example.com/v1"
export VLM_API_KEY="YOUR_PROXY_TOKEN"
export VLM_MODEL="YOUR_VISION_MODEL"
unset VLM_API_STYLE
unset VLM_USER_ID
unset VLM_ACCESS_KEY
unset VLM_QUOTA_ID
```

## Sanity Check

The following command should succeed before any benchmark run:

```bash
python -c 'from core.vlm_client import VLMClient; c = VLMClient(); print({"base_url": c.base_url, "model": c.model, "api_style": c.api_style})'
```

`summary.json` will store only non-secret runtime metadata:

- `vlm_base_url`
- `vlm_model`
- `vlm_api_style`
- `uses_alibaba_chat_api`
- presence flags for API credentials
