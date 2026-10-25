'''规则抽取：从一句话里，用最朴素的字符串规则抠出字段（离线、零网络）。

姓名按优先级尝试（误判优于漏判）：
1. 原文里直接出现「已有人脉的姓名」，最长优先；
2. 「认识 / 见了 / 遇到 / 和 / 跟 / 与」后面的候选，用姓氏表校验；
3. 全文扫描：先按常见大姓，再按常见小姓。

只抽「姓名 / 公司 / 职位 / 时间」；抽不到就留 None，绝不报错。
'''

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from rekindle.domain.dates import RELATIVE_DAYS
from rekindle.domain.models import ExtractedFields, ExtractSource
from rekindle.domain.surnames import BIG_SURNAMES, SMALL_SURNAMES, surname_length

_ROLE_KEYWORDS = (
    '后端', '前端', '算法', '产品', '运营', '设计', '测试',
    '人事', '运维', '架构', '数据', 'HR', '经理', '总监',
)

_NAME_STOP = frozenset('在是去来说聊见吃喝约工入认给让帮做他她我你们了的和跟与')


def _is_cjk(ch: str) -> bool:
    return 0x4E00 <= ord(ch) <= 0x9FFF


def _name_after(text: str, start: int) -> str | None:
    name = ''
    pos = start
    while pos < len(text) and text[pos] == '了':
        pos += 1
    for ch in text[pos:]:
        if ch in _NAME_STOP:
            break
        if _is_cjk(ch):
            if len(name) < 4:
                name += ch
            else:
                break
        else:
            break
    return name if 2 <= len(name) <= 4 else None


def _trim_to_name(candidate: str, extra_surnames: Iterable[str]) -> str | None:
    '''校验姓氏；4 字里若第 3 字又是姓，判为两个人，只取第一个。'''
    if len(candidate) < 2:
        return None
    if surname_length(candidate, extra_surnames) == 0:
        return None
    if len(candidate) >= 4 and surname_length(candidate[2:], extra_surnames) > 0:
        return candidate[:2]
    return candidate


def _match_known_name(text: str, known_names: Iterable[str]) -> str | None:
    '''优先级 1：原文里出现了已有人脉的姓名，最长优先。'''
    best: str | None = None
    for name in known_names:
        if len(name) >= 2 and name in text and (best is None or len(name) > len(best)):
            best = name
    return best


def _scan_name(
    text: str, allowed: frozenset[str], extra_surnames: Iterable[str]
) -> str | None:
    '''从任意位置找一个「姓 + 名」片段。'''
    for index, ch in enumerate(text):
        if ch not in allowed:
            continue
        candidate = _name_after(text, index)
        if not candidate:
            continue
        name = _trim_to_name(candidate, extra_surnames)
        if name:
            return name
    return None


def extract_name(text: str, known_names: Iterable[str] = ()) -> str | None:
    known = [name for name in known_names if len(name) >= 2]

    matched = _match_known_name(text, known)
    if matched:
        return matched

    extra = {name[0] for name in known}
    for hint in ('认识', '见了', '遇到', '和', '跟', '与'):
        idx = text.find(hint)
        if idx != -1:
            candidate = _name_after(text, idx + len(hint))
            if candidate:
                name = _trim_to_name(candidate, extra)
                if name:
                    return name

    return (
        _scan_name(text, BIG_SURNAMES, extra)
        or _scan_name(text, SMALL_SURNAMES, extra)
    )


def extract_company(text: str) -> str | None:
    for marker in ('工作', '入职', '实习'):
        m = text.find(marker)
        if m == -1:
            continue
        start = text.rfind('在', 0, m)
        if start != -1:
            seg = text[start + 1:m].strip()
            if 1 <= len(seg) <= 12:
                return seg
    m = text.find('公司')
    if m != -1:
        seg = ''
        for ch in reversed(text[:m]):
            if _is_cjk(ch):
                seg = ch + seg
            else:
                break
        if seg:
            return seg
    return None


def extract_role(text: str) -> str | None:
    for role in _ROLE_KEYWORDS:
        if role in text:
            return role
    return None


def extract_date(text: str, today: date) -> date | None:
    for keyword, offset in RELATIVE_DAYS.items():
        if keyword in text:
            return today + timedelta(days=offset)
    return None


def extract(
    text: str,
    today: date,
    known_names: Iterable[str] = (),
) -> ExtractedFields:
    return ExtractedFields(
        display_name=extract_name(text, known_names),
        company=extract_company(text),
        role=extract_role(text),
        occurred_at=extract_date(text, today),
        source=ExtractSource.RULE,
        confidence=0.5,
    )
