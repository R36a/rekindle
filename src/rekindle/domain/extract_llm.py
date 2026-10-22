'''LLM 抽取：让大模型理解一句话，按字段定义抽出结构化结果。

当前只保留代码与测试，CLI / GUI 不接入（LLM 暂停，见 README）。
本模块不 import httpx（只依赖 LlmClient 协议），便于用 Fake 客户端测试。
'''

from __future__ import annotations

import json
from datetime import date
from typing import Protocol

from rekindle.domain import extract_rule
from rekindle.domain.models import ExtractedFields, ExtractSource, FieldSpec


class LlmClient(Protocol):
    '''LLM 客户端的抽象（seam）。测试里用 Fake 替换。'''

    def complete(self, messages: list[dict[str, str]]) -> str:
        ...


class LlmError(RuntimeError):
    '''网络 / 超时等调用错误。'''


def build_system_prompt(fields: list[FieldSpec], today: date) -> str:
    lines = [
        '你是信息抽取助手，从用户一句话里抽取结构化信息，只输出一个 JSON 对象，不要解释。',
        f'今天是 {today}。相对日期（如下周三、上周）请按此换算。',
        '',
        '固定字段：',
        '- display_name: 姓名（字符串或 null）',
        '- company: 公司（字符串或 null）',
        '- role: 职位（字符串或 null）',
        '- occurred_at: 见面/认识时间（YYYY-MM-DD 或 null）',
        '- attributes: 自定义字段对象，key 只能用下面列出的字段 key',
        '',
        '规则：',
        '1. 抽不到就填 null 或省略，绝不编造；',
        '2. attributes 里不能出现下面没列出的 key；',
        '3. 只输出 JSON。',
    ]
    if fields:
        lines.append('')
        lines.append('自定义字段（attributes 里只能出现这些 key）：')
        for f in fields:
            desc = f' —— {f.description}' if f.description else ''
            lines.append(f'- {f.key}（{f.label}）{desc}')
    return '\n'.join(lines)


def _parse(raw: str, registered: set[str]) -> ExtractedFields:
    '''解析并校验 LLM 的 JSON；任何不合规都抛 ValueError（触发重试）。'''
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('返回的不是 JSON 对象')
    attrs = data.get('attributes') or {}
    if not isinstance(attrs, dict):
        raise ValueError('attributes 必须是对象')
    unknown = set(attrs) - registered
    if unknown:
        raise ValueError(f'出现了未注册的字段：{sorted(unknown)}')
    return ExtractedFields(**data)


def extract_llm(
    text: str,
    today: date,
    client: LlmClient,
    fields: list[FieldSpec],
) -> ExtractedFields:
    registered = {f.key for f in fields}
    messages: list[dict[str, str]] = [
        {'role': 'system', 'content': build_system_prompt(fields, today)},
        {'role': 'user', 'content': text},
    ]

    for attempt in range(2):
        raw = ''
        try:
            raw = client.complete(messages)
            result = _parse(raw, registered)
            result.source = ExtractSource.LLM
            return result
        except (LlmError, ValueError) as e:
            if attempt == 0:
                if raw:
                    messages.append({'role': 'assistant', 'content': raw})
                messages.append({'role': 'user', 'content': f'输出不合法：{e}，请只输出 JSON。'})

    return extract_rule.extract(text, today)
