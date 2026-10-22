'''日期输入的解析：ISO 与常见相对词，共用一张表。

CLI 的 --when 与离线抽取都从这里取规则，避免各写一套偏移量。
'''

from __future__ import annotations

from datetime import date, timedelta

# 关键词 → 相对今天的天数。
RELATIVE_DAYS: dict[str, int] = {
    '前天': -2,
    '昨天': -1,
    '今天': 0,
    '明天': 1,
    '后天': 2,
    '上周': -7,
    '下周': 7,
    '上个月': -30,
    '下个月': 30,
}

# 抽取时的判断顺序：更具体的词先判断。
RELATIVE_ORDER = (
    '前天', '昨天', '明天', '后天', '今天', '上周', '下周', '上个月', '下个月',
)


def parse_date_input(text: str, today: date) -> date | None:
    '''把用户输入解析成日期；认不出来返回 None。'''
    value = text.strip()
    if not value:
        return None
    if value in RELATIVE_DAYS:
        return today + timedelta(days=RELATIVE_DAYS[value])
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
