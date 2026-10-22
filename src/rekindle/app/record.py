'''记录用例：一句话 → 草稿 capture → 用户确认 → person / interaction。

两条硬规则：
1. 未确认不产生 interaction（P2「容错优先于全自动」）；
2. 同一 capture 只能确认一次（不变量 I2，数据库唯一索引兜底）。

离线抽取时会把「已导入人脉的姓氏」一起喂给规则，罕见姓（如「第五」）也能识别。
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
from rekindle.domain.models import (
    CaptureStatus,
    ExtractedFields,
    Interaction,
    Person,
)


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


def confirm(
    repo: RecordPort,
    capture_id: int,
    *,
    now: datetime,
    name: str | None = None,
    company: str | None = None,
    role: str | None = None,
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
    occurred_at = datetime.combine(occurred_on or parsed.occurred_at or now.date(), time.min)

    # 消歧只做两档：别名精确、姓名精确。宁可多建，不可错并。
    existing = None if create_new else _match_person(repo, display_name)

    with repo.transaction():
        if existing is None:
            companies = (
                {occurred_at.date(): resolved_company} if resolved_company else {}
            )
            person_id = repo.add_person(
                Person(
                    display_name=display_name,
                    companies=companies,
                    role=resolved_role,
                    last_contact_at=occurred_at,
                )
            )
            created_new = True
            person_name = display_name
        else:
            if existing.id is None:
                raise PersonNotFound(-1)
            person_id = existing.id
            companies = dict(existing.companies)
            if resolved_company:
                companies[occurred_at.date()] = resolved_company
            repo.update_person(
                existing.model_copy(
                    update={
                        'companies': companies,
                        'role': resolved_role or existing.role,
                        'last_contact_at': occurred_at,
                    }
                )
            )
            created_new = False
            person_name = existing.display_name

        interaction_id = repo.add_interaction(
            Interaction(
                person_id=person_id,
                capture_id=capture_id,
                occurred_at=occurred_at,
                summary=capture.raw_text[:500],
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


def _match_person(repo: RecordPort, name: str) -> Person | None:
    return repo.find_person_by_alias(name) or repo.find_person_by_name(name)
