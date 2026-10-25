'''编辑用例：人物资料、交往记录、归档。

所有编辑都是用户显式操作；姓名与摘要不能为空。
修改交往日期不会联动公司历史（按产品决策：两边独立维护）。
'''

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from rekindle.app.ports import Repo
from rekindle.domain.dates import at_midnight, latest_contact
from rekindle.domain.errors import PersonNotFound
from rekindle.domain.fields import normalize_fields
from rekindle.domain.limits import SUMMARY_MAX_LENGTH
from rekindle.domain.models import Interaction, Person
from rekindle.domain.text import clean_optional, require_name


@dataclass(frozen=True)
class PersonEdit:
    display_name: str
    role: str | None
    notes: str | None
    companies: dict[date, str]
    fields: dict[str, list[str]]


def save_person(repo: Repo, person_id: int, edit: PersonEdit) -> Person:
    person = repo.get_person(person_id)
    if person is None:
        raise PersonNotFound(person_id)
    # 姓名合法性与 record 走同一个函数：model_copy 不跑校验，必须在这之前拦。
    name = require_name(edit.display_name)

    companies = {
        day: company.strip()
        for day, company in edit.companies.items()
        if company.strip()
    }
    cleaned_fields = normalize_fields(edit.fields)

    updated = person.model_copy(
        update={
            'display_name': name,
            'role': clean_optional(edit.role),
            'notes': clean_optional(edit.notes),
            'companies': companies,
            'fields': cleaned_fields,
        }
    )
    repo.update_person(updated)
    return updated


def save_interaction(
    repo: Repo,
    interaction: Interaction,
    *,
    occurred_on: date,
    summary: str,
) -> Interaction:
    text = summary.strip()
    if not text:
        raise ValueError('记录内容不能为空')
    if interaction.id is None:
        raise ValueError('需要 interaction.id')

    updated = interaction.model_copy(
        update={
            'occurred_at': at_midnight(occurred_on),
            'summary': text[:SUMMARY_MAX_LENGTH],
        }
    )
    repo.update_interaction(updated)
    _sync_last_contact(repo, interaction.person_id)
    return updated


def delete_interaction(repo: Repo, interaction: Interaction) -> None:
    if interaction.id is None:
        raise ValueError('需要 interaction.id')
    repo.delete_interaction(interaction.id)
    _sync_last_contact(repo, interaction.person_id)


def archive_person(repo: Repo, person_id: int) -> None:
    repo.archive_person(person_id)


def _sync_last_contact(repo: Repo, person_id: int) -> None:
    '''交往记录增删改后，把「最近联系」重算成最大日期。'''
    person = repo.get_person(person_id)
    if person is None:
        return
    interactions = repo.list_interactions(person_id)
    repo.update_person(
        person.model_copy(
            update={
                'last_contact_at': latest_contact(
                    item.occurred_at for item in interactions
                )
            }
        )
    )
