'''日期输入解析：ISO 与相对词共用一张表。'''

from __future__ import annotations

from datetime import date

from rekindle.domain.dates import parse_date_input

TODAY = date(2026, 10, 22)


def test_ISO日期() -> None:
    assert parse_date_input('2026-10-15', TODAY) == date(2026, 10, 15)


def test_相对日期() -> None:
    assert parse_date_input('今天', TODAY) == TODAY
    assert parse_date_input('昨天', TODAY) == date(2026, 10, 21)
    assert parse_date_input('前天', TODAY) == date(2026, 10, 20)
    assert parse_date_input('上周', TODAY) == date(2026, 10, 15)


def test_去空白() -> None:
    assert parse_date_input('  昨天  ', TODAY) == date(2026, 10, 21)


def test_认不出来返回None() -> None:
    assert parse_date_input('不是日期', TODAY) is None
    assert parse_date_input('', TODAY) is None
