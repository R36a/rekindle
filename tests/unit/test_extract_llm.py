'''LLM 抽取的测试：用 Fake 客户端模拟模型，不联网。'''

from __future__ import annotations

import json
from datetime import date

from rekindle.domain.extract_llm import LlmError, extract_llm
from rekindle.domain.models import ExtractSource, FieldSpec

TODAY = date(2026, 10, 21)


class FakeLlmClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        if not self.responses:
            raise LlmError('没有更多预设响应')
        return self.responses.pop(0)


class FailingLlmClient:
    def complete(self, messages: list[dict[str, str]]) -> str:
        raise LlmError('网络断了')


def test_正常抽取_固定字段() -> None:
    client = FakeLlmClient([
        json.dumps({
            'display_name': '张三',
            'company': '字节',
            'occurred_at': '2026-10-14',
        }),
    ])
    result = extract_llm('上周和张三在字节工作', TODAY, client, [])

    assert result.display_name == '张三'
    assert result.company == '字节'
    assert result.occurred_at == date(2026, 10, 14)
    assert result.source is ExtractSource.LLM


def test_自定义字段_只填已注册() -> None:
    fields = [FieldSpec(key='hobby', label='爱好', description='这个人的爱好')]
    client = FakeLlmClient([
        json.dumps({'display_name': '张三', 'attributes': {'hobby': '打篮球'}}),
    ])
    result = extract_llm('张三爱打篮球', TODAY, client, fields)

    assert result.attributes == {'hobby': '打篮球'}


def test_非法JSON_重试一次后成功() -> None:
    client = FakeLlmClient(['不是JSON', json.dumps({'display_name': '张三'})])
    result = extract_llm('张三', TODAY, client, [])

    assert result.display_name == '张三'
    assert client.calls == 2


def test_非法JSON_两次失败_降级规则() -> None:
    client = FakeLlmClient(['不是JSON', '还是不是JSON'])
    result = extract_llm('和张三吃饭', TODAY, client, [])

    assert result.source is ExtractSource.RULE
    assert result.display_name == '张三'


def test_网络错误_降级规则() -> None:
    client = FailingLlmClient()
    result = extract_llm('和张三吃饭', TODAY, client, [])

    assert result.source is ExtractSource.RULE
    assert result.display_name == '张三'


def test_未注册字段_被拒绝后重试() -> None:
    client = FakeLlmClient([
        json.dumps({'display_name': '张三', 'attributes': {'未知字段': 'x'}}),
        json.dumps({'display_name': '张三', 'attributes': {}}),
    ])
    result = extract_llm('张三', TODAY, client, [])

    assert result.attributes == {}
    assert client.calls == 2
