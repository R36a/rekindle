'''用 httpx 调 DeepSeek（OpenAI 兼容）接口。'''

from __future__ import annotations

import httpx

from rekindle.domain.extract_llm import LlmError

DEFAULT_BASE_URL = 'https://api.deepseek.com/chat/completions'


class HttpLlmClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = 'deepseek-flash',
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {'model': self.model, 'temperature': 0, 'messages': messages}
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.base_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return str(data['choices'][0]['message']['content'])
        except httpx.HTTPError as e:
            raise LlmError(f'LLM 调用失败：{e}') from e
