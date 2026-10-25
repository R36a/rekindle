'''可选文本清洗：全项目唯一的「trim → None」口径。'''

from __future__ import annotations

from rekindle.domain.text import clean_optional


def test_空白与None一律归为None() -> None:
    assert clean_optional(None) is None
    assert clean_optional('') is None
    assert clean_optional('   ') is None
    assert clean_optional('\t\n') is None


def test_去掉首尾空白但保留中间内容() -> None:
    assert clean_optional('  腾讯 ') == '腾讯'
    assert clean_optional('\n后端\t') == '后端'
