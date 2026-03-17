# LLM Chat API 使用说明

## 1. 接口地址

POST https://llm-chat-api.alibaba-inc.com/v1/api/chat

---

## 2. 文本调用（最简单）

### curl

curl "https://llm-chat-api.alibaba-inc.com/v1/api/chat" \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.4-0305-global",
    "prompt": "Explain reinforcement learning in one paragraph.",
    "user_id": "your_user_id",
    "access_key": "your_access_key",
    "quota_id": "your_quota_id",
    "app": "llm_application"
  }'

---

## 3. 多轮对话

"prompt": [
  {"role": "user", "content": "你好"},
  {"role": "assistant", "content": "你好"},
  {"role": "user", "content": "我刚刚说了什么？"}
]

---

## 4. 图文输入

"prompt": [
  {
    "role": "user",
    "content": [
      {"type": "text", "text": "What is in this image?"},
      {
        "type": "image_url",
        "image_url": {
          "url": "https://example.com/image.jpg"
        }
      }
    ]
  }
]

---

## 5. base64 图片（推荐）

{
  "type": "image_url",
  "image_url": {
    "url": "data:image/jpeg;base64,xxxx"
  }
}

---

## 6. Python 示例

import requests

url = "https://llm-chat-api.alibaba-inc.com/v1/api/chat"

headers = {
    "Authorization": "YOUR_TOKEN",
    "Content-Type": "application/json"
}

payload = {
    "model": "gpt-5.4-0305-global",
    "prompt": "Explain reinforcement learning in one paragraph.",
    "user_id": "your_user_id",
    "access_key": "your_access_key",
    "quota_id": "your_quota_id",
    "app": "llm_application"
}

resp = requests.post(url, headers=headers, json=payload)
print(resp.json()["data"]["message"])

---

## 7. 说明

- 输入统一使用 prompt
- 单轮：字符串
- 多轮：数组
- 图文：content 内再嵌数组
