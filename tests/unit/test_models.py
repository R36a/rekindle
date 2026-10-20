"""模型层的测试：验证"字段规则"是否真的生效。

pytest 的用法只有三条：

1. 函数名以 `test_` 开头，就会被自动发现并执行；
2. 用 `assert 某个条件` 表达"我认为这里应该成立"，不成立就报红；
3. 用 `pytest.raises(错误类型)` 断言"这里应该报错"。

运行：`pytest`
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from rekindle.domain.models import (
    Capture,
    CaptureStatus,
    ExtractedFields,
    ExtractSource,
)


def test_抽取正常数据并检查默认值() -> None:
    """正常数据能建对象；没传的字段用默认值。"""
    fields = ExtractedFields(
        display_name="张三",
        company="字节",
        occurred_at=date(2026, 10, 14),
    )

    assert fields.display_name == "张三"
    assert fields.company == "字节"
    assert fields.occurred_at == date(2026, 10, 14)
    # 下面三个都是"没传"时的默认值
    assert fields.confidence == 0.5
    assert fields.source is ExtractSource.RULE
    assert fields.promise is None


def test_多传未知字段会报错() -> None:
    """extra="forbid"：拼错的字段名不该被静默忽略。

    这里用 `**字典` 传参，是为了绕开类型检查（人写代码时不会这么写，
    但模型返回 JSON 时可能多出字段，所以要测这个行为）。
    """
    with pytest.raises(ValidationError):
        ExtractedFields(**{"display_name": "张三", "nickname": "小张"})


def test_空字符串自动变成None() -> None:
    """空字符串 / 纯空格 → None，避免"没有"有三种写法。"""
    fields = ExtractedFields(display_name="张三", company="   ", role="")

    assert fields.company is None
    assert fields.role is None


@pytest.mark.parametrize("bad_cadence", [0, 366, -5])
def test_联系间隔超出范围会报错(bad_cadence: int) -> None:
    """cadence_days 只允许 1~365 天。"""
    with pytest.raises(ValidationError):
        ExtractedFields(display_name="张三", cadence_days=bad_cadence)


def test_原始输入默认是草稿且不能为空() -> None:
    """Capture 刚创建时是 draft；raw_text 去空格后不能为空。"""
    capture = Capture(raw_text="和张三吃饭", created_at=datetime(2026, 10, 21, 9, 0))

    assert capture.status is CaptureStatus.DRAFT
    assert capture.id is None          # 还没入库
    assert capture.parsed is None

    with pytest.raises(ValidationError):
        Capture(raw_text="   ", created_at=datetime(2026, 10, 21, 9, 0))
