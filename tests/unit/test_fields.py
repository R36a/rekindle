'''联系方式规范化：去空白、去空值、去重，record 与 edit 共用。'''

from __future__ import annotations

from rekindle.domain.fields import normalize_fields, normalize_values


def test_去空白去空值并去重且保持顺序() -> None:
    assert normalize_values([' wx1 ', 'wx1', '', '  ', 'wx2']) == ['wx1', 'wx2']


def test_空字段整个丢掉() -> None:
    assert normalize_fields({'wechat': [' ', ''], 'qq': [' 123 ']}) == {'qq': ['123']}
    assert normalize_fields(None) == {}
