'''规则抽取：从一句话里，用最朴素的字符串规则抠出字段（离线、零网络）。

设计对应 docs/设计细节.md §2、§9、§10：
- 只抽「系统字段 + 内置属性字段 + 单条待办」；
- 用户自定义字段这里不做（交给 LLM，T4）；
- 抽不到就留 None，绝不报错——后面有「预填+确认」兜底。

刻意不用正则、不用网络，只用 str.find / 切片 / 码点判断，方便零基础读懂。
'''

from __future__ import annotations

from datetime import date, timedelta

from rekindle.domain.models import ExtractedFields, ExtractSource, TodoDraft

_ROLE_KEYWORDS = (
    '后端', '前端', '算法', '产品', '运营', '设计', '测试',
    '人事', '运维', '架构', '数据', 'HR', '经理', '总监',
)

_TODO_TRIGGERS = ('答应', '说好', '承诺', '约好', '回头', '下次')

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


def extract_name(text: str) -> str | None:
    for hint in ('认识', '见了', '遇到', '和', '跟', '与'):
        idx = text.find(hint)
        if idx != -1:
            name = _name_after(text, idx + len(hint))
            if name:
                return name
    return None


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
    if '前天' in text:
        return today - timedelta(days=2)
    if '昨天' in text:
        return today - timedelta(days=1)
    if '明天' in text:
        return today + timedelta(days=1)
    if '后天' in text:
        return today + timedelta(days=2)
    if '今天' in text:
        return today
    if '上周' in text:
        return today - timedelta(days=7)
    if '下周' in text:
        return today + timedelta(days=7)
    if '上个月' in text:
        return today - timedelta(days=30)
    if '下个月' in text:
        return today + timedelta(days=30)
    return None


def extract_cadence(text: str) -> int | None:
    if '每周' in text:
        return 7
    if '每月' in text:
        return 30
    if '每年' in text:
        return 365
    if '常联系' in text or '保持联系' in text or '经常联系' in text:
        return 30
    return None


def _trim(s: str) -> str:
    s = s.strip()
    while s and s[-1] in '，。！？,.!?了~～ ':
        s = s[:-1]
    return s.strip()


def extract_todos(text: str, today: date, name: str | None) -> list[TodoDraft]:
    for trigger in _TODO_TRIGGERS:
        idx = text.find(trigger)
        if idx == -1:
            continue
        title = _trim(text[idx + len(trigger):])
        if not title:
            continue
        due = extract_date(title, today) or extract_date(text, today)
        people = [name] if name else []
        return [TodoDraft(title=title, due_on=due, people_names=people)]
    return []


def extract(text: str, today: date) -> ExtractedFields:
    name = extract_name(text)
    return ExtractedFields(
        display_name=name,
        company=extract_company(text),
        role=extract_role(text),
        occurred_at=extract_date(text, today),
        cadence_days=extract_cadence(text),
        todos=extract_todos(text, today, name),
        source=ExtractSource.RULE,
        confidence=0.5,
    )
