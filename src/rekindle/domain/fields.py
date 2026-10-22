'''默认属性字段：联系方式这类可扩展的信息。

字段由注册表（field 表）管理，这里只是初始四项；AI / 抽取只能在注册表内填值，
不新增字段（见 docs/设计细节.md §9）。
'''

from __future__ import annotations

from rekindle.domain.models import FieldSpec

DEFAULT_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(key='wechat', label='微信', description='微信号'),
    FieldSpec(key='qq', label='QQ', description='QQ 号'),
    FieldSpec(key='email', label='邮箱', description='邮箱地址'),
    FieldSpec(key='phone', label='电话', description='手机号'),
)

FIELD_LABELS: dict[str, str] = {field.key: field.label for field in DEFAULT_FIELDS}