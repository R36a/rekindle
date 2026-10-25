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
from datetime import date, datetime

from rekindle.app.ports import Repo
from rekindle.domain import extract_rule
from rekindle.domain.dates import at_midnight, latest_contact, resolve_day
from rekindle.domain.errors import (
    AlreadyConfirmed,
    CaptureNotFound,
    EmptyCapture,
    PersonNotFound,
)
from rekindle.domain.fields import merge_fields, normalize_fields
from rekindle.domain.limits import SUMMARY_MAX_LENGTH
from rekindle.domain.models import (
    CaptureStatus,
    ExtractedFields,
    Interaction,
    Person,
)
from rekindle.domain.person_schema import FIELD_BY_KEY, SUMMARY_FIELDS
from rekindle.domain.text import clean_optional, require_name

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


def record(repo: Repo, text: str, now: datetime) -> RecordedCapture:
    '''规则抽取并保存草稿。

    原话先裁剪：模型读回来时本来就会被 strip（_StrictModel 的 str_strip_whitespace），
    写入口先裁，库里的值与模型才一致。空白原话在这里就拒绝——写进去读不出来，
    会让后续 confirm / 详情页抛校验错误。

    额外把已导入人脉的姓氏喂给规则：常见姓走内置表，罕见姓靠「线上已有的人」
    学出来——库里有「第五明」时，下次就能抽到「第五」。
    '''
    raw_text = text.strip()
    if not raw_text:
        raise EmptyCapture()

    parsed = extract_rule.extract(raw_text, now.date(), repo.list_person_names())
    # 日期字段默认今天；用户可在确认表单里改。
    parsed.occurred_at = resolve_day(now.date(), parsed.occurred_at)
    capture_id = repo.add_capture(raw_text, now, parsed)
    return RecordedCapture(capture_id=capture_id, parsed=parsed)


def manual(
    repo: Repo,
    *,
    now: datetime,
    display_name: str,
    company: str | None = None,
    role: str | None = None,
    fields: dict[str, list[str]] | None = None,
    occurred_on: date | None = None,
) -> ConfirmResult:
    '''没有原话时的入库：字段直接写库，记录文本自动生成。

    参数名与 `Person` / 字段注册表一致（`display_name`），只有 CLI 的 `--name`
    和 HTTP body 的 `name` 是对外拼写。姓名必填；日期默认「入库当天」。
    '''
    name = require_name(display_name)

    resolved_company = clean_optional(company)
    resolved_role = clean_optional(role)
    extra_fields = normalize_fields(fields)
    occurred_at = at_midnight(resolve_day(now.date(), occurred_on))

    return _commit(
        repo,
        display_name=name,
        company=resolved_company,
        role=resolved_role,
        fields=extra_fields,
        occurred_at=occurred_at,
        now=now,
        summary=_manual_summary(
            name,
            occurred_at.date(),
            resolved_company,
            resolved_role,
            extra_fields,
        ),
    )


def confirm(
    repo: Repo,
    capture_id: int,
    *,
    now: datetime,
    display_name: str | None = None,
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
    # 用户没给（None / 全空白）就用抽取结果；合法性只由 require_name 一处判。
    name = require_name(clean_optional(display_name) or parsed.display_name)

    resolved_company = (
        clean_optional(company) if company is not None else clean_optional(parsed.company)
    )
    resolved_role = (
        clean_optional(role) if role is not None else clean_optional(parsed.role)
    )
    extra_fields = normalize_fields(fields)
    occurred_at = at_midnight(resolve_day(now.date(), occurred_on, parsed.occurred_at))
    # 原话一定非空（record 入口已拦），记录文本就是原话本身。
    summary = capture.raw_text.strip()

    return _commit(
        repo,
        display_name=name,
        company=resolved_company,
        role=resolved_role,
        fields=extra_fields,
        occurred_at=occurred_at,
        now=now,
        summary=summary,
        capture_id=capture_id,
        create_new=create_new,
    )


def _commit(
    repo: Repo,
    *,
    display_name: str,
    company: str | None,
    role: str | None,
    fields: dict[str, list[str]],
    occurred_at: datetime,
    now: datetime,
    summary: str,
    capture_id: int | None = None,
    create_new: bool = False,
) -> ConfirmResult:
    '''一次入库：建/并人 + 写交往记录（+ 完成草稿），全在一个事务里。

    manual 与 confirm 只有「摘要怎么来、要不要完结草稿」不同，
    写入流程共用这一份实现——以前是两个各 20 行的复制块。
    '''
    with repo.atomic():
        person_id, person_name, created_new = _upsert_person(
            repo,
            display_name=display_name,
            company=company,
            role=role,
            fields=fields,
            occurred_at=occurred_at,
            create_new=create_new,
        )
        interaction_id = repo.add_interaction(
            Interaction(
                person_id=person_id,
                capture_id=capture_id,
                occurred_at=occurred_at,
                summary=summary[:SUMMARY_MAX_LENGTH],
                created_at=now,
            )
        )
        if capture_id is not None:
            repo.confirm_capture(capture_id, person_id)

    return ConfirmResult(
        person_id=person_id,
        person_name=person_name,
        created_new=created_new,
        interaction_id=interaction_id,
    )


def _upsert_person(
    repo: Repo,
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
    merged_fields = merge_fields(existing.fields, fields)
    repo.update_person(
        existing.model_copy(
            update={
                'companies': companies,
                'fields': merged_fields,
                'role': role or existing.role,
                # 补录历史记录不能把「最近联系」改早：规则只有 latest_contact 一处。
                'last_contact_at': latest_contact(
                    (existing.last_contact_at, occurred_at)
                ),
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
    '''没有原话时，把填过的字段写成一句可读的记录文本。

    有哪些字段、按什么顺序写，全部来自 `person_schema.SUMMARY_FIELDS`；
    「日期」属于交往记录（不是 Person 字段），固定跟在姓名之后。
    '''
    values: dict[str, str] = {}
    if company:
        values['company'] = company
    if role:
        values['role'] = role
    for key, items in fields.items():
        values[key] = '、'.join(items)

    parts = [
        f'{FIELD_BY_KEY["display_name"].label}：{name}',
        f'日期：{day.isoformat()}',
    ]
    parts.extend(
        f'{field.label}：{values[field.key]}'
        for field in SUMMARY_FIELDS
        if field.key != 'display_name' and values.get(field.key)
    )
    return MANUAL_PREFIX + '，'.join(parts)


def _match_person(repo: Repo, name: str) -> Person | None:
    return repo.find_person_by_alias(name) or repo.find_person_by_name(name)
