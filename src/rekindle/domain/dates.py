'''日期输入的解析：ISO 与常见相对词，共用一张表。

CLI 的 --when 与离线抽取都从这里取规则，避免各写一套偏移量。
'''

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

# 关键词 → 相对今天的天数。
# 遍历顺序就是 dict 的插入顺序：这些词两两不互为子串，所以顺序不影响结果，
# 不需要再单独维护一张「判断顺序」表。
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


def at_midnight(day: date) -> datetime:
    '''日期 → 当天 00:00；记录时间统一用零点。'''
    return datetime.combine(day, time.min)


def resolve_day(default: date, *candidates: date | None) -> date:
    '''取第一个非 None 的候选日期；全为空时用 default。'''
    for day in candidates:
        if day is not None:
            return day
    return default


def latest_contact(times: Iterable[datetime | None]) -> datetime | None:
    '''最近联系时间 = 所有已知时间里的最大值；None 不参与比较。

    「最近联系」这条事实只有一个实现：record 合并已有的人、
    edit 改/删交往记录后的重算，都调用这里。
    以前 record 直接用「本次日期」覆盖，补录一条更早的历史记录会把
    last_contact_at 改早，列表的「最近联系优先」排序就错了。
    '''
    return max((moment for moment in times if moment is not None), default=None)
