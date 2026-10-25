'''属性字段清单：联系方式这类可扩展的信息。

这里是字段集合的**唯一来源**（`FIELD_KEYS`）：UI、CLI 参数与仓储校验都从这份清单派生。
以前还有一张 field 表存同样四项，但它的 label / type / description 没有任何读者，
等于同一事实存两份、还会漂移（UI 认常量、仓储认表）——v7 起删表，只留这份常量。
字段增删仍只由用户做，AI / 抽取只能在这份清单内填值（见 docs/设计细节.md §9）。
'''

from __future__ import annotations

from collections.abc import Iterable, Mapping

from rekindle.domain.models import FieldSpec

DEFAULT_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(key='wechat', label='微信', description='微信号'),
    FieldSpec(key='qq', label='QQ', description='QQ 号'),
    FieldSpec(key='email', label='邮箱', description='邮箱地址'),
    FieldSpec(key='phone', label='电话', description='手机号'),
)

FIELD_KEYS: frozenset[str] = frozenset(spec.key for spec in DEFAULT_FIELDS)


def normalize_values(values: Iterable[str]) -> list[str]:
    '''去空白、丢掉空值、去重，保持输入顺序。'''
    cleaned: list[str] = []
    for value in values:
        text = value.strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def normalize_fields(
    fields: Mapping[str, Iterable[str]] | None,
) -> dict[str, list[str]]:
    '''按字段规范化；规范化后为空的字段整个丢掉。'''
    normalized: dict[str, list[str]] = {}
    for key, values in (fields or {}).items():
        cleaned = normalize_values(values)
        if cleaned:
            normalized[key] = cleaned
    return normalized


def merge_fields(
    existing: Mapping[str, Iterable[str]],
    incoming: Mapping[str, Iterable[str]],
) -> dict[str, list[str]]:
    '''把 incoming 追加进 existing：同 key 合并、去重、保持顺序。

    新增联系方式的唯一实现：record 合并已有人、编辑窗「添加」都走这里，
    不再各自写一遍 `if value not in values: values.append(value)`。
    '''
    merged = normalize_fields(existing)
    for key, values in incoming.items():
        merged[key] = normalize_values([*merged.get(key, []), *values])
    return {key: values for key, values in merged.items() if values}
