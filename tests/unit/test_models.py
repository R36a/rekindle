'''模型层的测试：验证字段规则是否真的生效。'''

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from rekindle.domain.models import (
    Capture,
    CaptureStatus,
    ExtractedFields,
    ExtractSource,
    RepeatRule,
    TodoDraft,
)


def test_抽取正常数据并检查默认值() -> None:
    fields = ExtractedFields(
        display_name='张三',
        company='字节',
        occurred_at=date(2026, 10, 14),
    )

    assert fields.display_name == '张三'
    assert fields.company == '字节'
    assert fields.occurred_at == date(2026, 10, 14)
    assert fields.confidence == 0.5
    assert fields.source is ExtractSource.RULE
    assert fields.todos == []


def test_多传未知字段会报错() -> None:
    with pytest.raises(ValidationError):
        ExtractedFields(**{'display_name': '张三', 'nickname': '小张'})


def test_空字符串自动变成None() -> None:
    fields = ExtractedFields(display_name='张三', company='   ', role='')

    assert fields.company is None
    assert fields.role is None


@pytest.mark.parametrize('bad_cadence', [0, 366, -5])
def test_联系间隔超出范围会报错(bad_cadence: int) -> None:
    with pytest.raises(ValidationError):
        ExtractedFields(display_name='张三', cadence_days=bad_cadence)


def test_原始输入默认是草稿且不能为空() -> None:
    capture = Capture(raw_text='和张三吃饭', created_at=datetime(2026, 10, 21, 9, 0))

    assert capture.status is CaptureStatus.DRAFT
    assert capture.id is None
    assert capture.parsed is None

    with pytest.raises(ValidationError):
        Capture(raw_text='   ', created_at=datetime(2026, 10, 21, 9, 0))


def test_待办草稿默认不重复() -> None:
    todo = TodoDraft(title='帮张三看简历')

    assert todo.repeat_rule is RepeatRule.NONE
    assert todo.due_on is None
    assert todo.people_names == []
