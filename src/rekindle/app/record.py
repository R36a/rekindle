'''记录用例：一句话 → 草稿 capture → 用户确认 → person / interaction。

支持两种入口：
1. 有原话：record() 生成草稿，confirm() 确认入库；
2. 没有原话：manual() 直接用字段入库（姓名必填，日期默认入库当天）。

两条硬规则不变：
- 未确认不产生 interaction；
- 同一 capture 只能确认一次（数据库唯一索引兜底）。
'''

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from rekindle.app.ports import RecordPort
from rekindle.domain import extract_rule
from rekindle.domain.errors import (
    AlreadyConfirmed,
    CaptureNotFound,
    MissingName,
    PersonNotFound,
)
from rekindle.domain.fields import FIELD_LABELS
from rekindle.domain.models import (
    CaptureStatus,
    ExtractedFields,
    Interaction,
    Person,
)

MANUAL_PREFIX = '用户输入了：'


@dataclass(frozen=True)
class RecordedCapture:
    capture_id: int
    parsed: ExtractedFields


@dataclass(frozen=True)
class ConfirmResult:
    person_id: int
    person_name: str
    created_new: bool
    interaction_id: int


def record(repo: RecordPort, text: str, now: datetime) -> RecordedCapture:
    '''规则抽取并保存草稿。

    额外把已导入人脉的姓氏喂给规则：常见姓走内置表，罕见姓靠「线上已有的人」
    学出来——库里有「第五明」时，下次就能抽到「第五」。
    '''
    parsed = extract_rule.extract(text, now.date(), repo.list_person_names())
    if parsed.occurred_at is None:
        # 日期字段默认今天；用户可在确认表单里改。
        parsed.occurred_at = now.date()
    capture_id = repo.add_capture(text, now, parsed)
    return RecordedCapture(capture_id=capture_id, parsed=parsed)


def manual(
    repo: RecordPort,
    *,
    now: datetime,
    name: str,
    company: str | None = None,
    role: str | None = None,
    fields: dict[str, list[str]] | None = None,
    occurred_on: date | None = None,
) -> ConfirmResult:
    '''没有原话时的入库：字段直接写库，记录文本自动生成。

    姓名必填；日期默认「入库当天」，也可以在表单里改。
    '''
    display_name = name.strip()
    if not display_name:
        raise MissingName('缺少姓名：姓名是必填字段')

    resolved_company = (company or '').strip() or None
    resolved_role = (role or '').strip() or None
    extra_fields = _normalize_fields(fields)
    occurred_at = datetime.combine(occurred_on or now.date(), time.min)
    summary = _manual_summary(
        display_name,
        occurred_at.date(),
        resolved_company,
        resolved_role,
        extra_fields,
    )[:500]

    with repo.transaction():
        person_id, person_name, created_new = _upsert_person(
            repo,
            display_name=display_name,
            company=resolved_company,
            role=resolved_role,
            fields=extra_fields,
            occurred_at=occurred_at,
        )
        interaction_id = repo.add_interaction(
            Interaction(
                person_id=person_id,
                capture_id=None,
                occurred_at=occurred_at,
                summary=summary,
                created_at=now,
            )
        )

    return ConfirmResult(
        person_id=person_id,
        person_name=person_name,
        created_new=created_new,
        interaction_id=interaction_id,
    )


def confirm(
    repo: RecordPort,
    capture_id: int,
    *,
    now: datetime,
    name: str | None = None,
    company: str | None = None,
    role: str | None = None,
    fields: dict[str, list[str]] | None = None,
    occurred_on: date | None = None,
    create_new: bool = False,
) -> ConfirmResult:
    '''把草稿变成一条真实记录。

    参数都是「用户改过的字段」；没传就用抽取结果。所有写入在一个事务里完成，
    中途任何一步失败都会整体回滚（P0：不丢数据、不留半条记录）。
    '''
    capture = repo.get_capture(capture_id)
    if capture is None:
        raise CaptureNotFound(capture_id)
    if capture.status is not CaptureStatus.DRAFT:
        raise AlreadyConfirmed(capture_id)

    parsed = capture.parsed or ExtractedFields()
    display_name = (name or parsed.display_name or '').strip()
    if not display_name:
        raise MissingName('缺少姓名：请用 --name 指定后重试')

    resolved_company = company if company is not None else parsed.company
    resolved_role = role if role is not None else parsed.role
    extra_fields = _normalize_fields(fields)
    occurred_at = datetime.combine(occurred_on or parsed.occurred_at or now.date(), time.min)
    summary = capture.raw_text.strip() or _manual_summary(
        display_name,
        occurred_at.date(),
        resolved_company,
        resolved_role,
        extra_fields,
    )

    with repo.transaction():
        person_id, person_name, created_new = _upsert_person(
            repo,
            display_name=display_name,
            company=resolved_company,
            role=resolved_role,
            fields=extra_fields,
            occurred_at=occurred_at,
            create_new=create_new,
        )
        interaction_id = repo.add_interaction(
            Interaction(
                person_id=person_id,
                capture_id=capture_id,
                occurred_at=occurred_at,
                summary=summary[:500],
                created_at=now,
            )
        )
        repo.confirm_capture(capture_id, person_id)

    return ConfirmResult(
        person_id=person_id,
        person_name=person_name,
        created_new=created_new,
        interaction_id=interaction_id,
    )


def _normalize_fields(
    fields: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    '''去掉空值、去重，保持输入顺序。'''
    normalized: dict[str, list[str]] = {}
    for key, values in (fields or {}).items():
        cleaned: list[str] = []
        for value in values:
            text = value.strip()
            if text and text not in cleaned:
                cleaned.append(text)
        if cleaned:
            normalized[key] = cleaned
    return normalized


def _upsert_person(
    repo: RecordPort,
    *,
    display_name: str,
    company: str | None,
    role: str | None,
    fields: dict[str, list[str]],
    occurred_at: datetime,
    create_new: bool = False,
) -> tuple[int, str, bool]:
    '''新建或合并一个人；调用方负责事务。'''
    existing = None if create_new else _match_person(repo, display_name)

    if existing is None:
        companies = {occurred_at.date(): company} if company else {}
        person_id = repo.add_person(
            Person(
                display_name=display_name,
                companies=companies,
                fields=fields,
                role=role,
                last_contact_at=occurred_at,
            )
        )
        return person_id, display_name, True

    if existing.id is None:
        raise PersonNotFound(-1)
    companies = dict(existing.companies)
    if company:
        companies[occurred_at.date()] = company
    merged_fields = {key: list(values) for key, values in existing.fields.items()}
    for key, values in fields.items():
        merged = merged_fields.setdefault(key, [])
        for value in values:
            if value not in merged:
                merged.append(value)
    repo.update_person(
        existing.model_copy(
            update={
                'companies': companies,
                'fields': merged_fields,
                'role': role or existing.role,
                'last_contact_at': occurred_at,
            }
        )
    )
    return existing.id, existing.display_name, False


def _manual_summary(
    name: str,
    day: date,
    company: str | None,
    role: str | None,
    fields: dict[str, list[str]],
) -> str:
    '''没有原话时，把填过的字段写成一句可读的记录文本。'''
    parts = [f'姓名：{name}', f'日期：{day.isoformat()}']
    if company:
        parts.append(f'公司：{company}')
    if role:
        parts.append(f'职位：{role}')
    for key, label in FIELD_LABELS.items():
        values = fields.get(key)
        if values:
            parts.append(f'{label}：' + '、'.join(values))
    return MANUAL_PREFIX + '，'.join(parts)


def _match_person(repo: RecordPort, name: str) -> Person | None:
    return repo.find_person_by_alias(name) or repo.find_person_by_name(name)