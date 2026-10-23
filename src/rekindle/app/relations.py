'''关系用例：添加/删除「谁认识谁」，以及记录「谁介绍谁」。

一条硬规则：介绍关系不等于认识关系。新增联系人时只记 introduced，
不会自动替他补一条「朋友」边；用户要认识关系，必须自己选类型。
'''

from __future__ import annotations

from datetime import datetime

from rekindle.app.ports import RelationPort
from rekindle.domain.errors import InvalidRelation, PersonNotFound
from rekindle.domain.models import Relation
from rekindle.domain.relations import SELECTABLE_KINDS, RelationKind


def add_relation(
    repo: RelationPort,
    *,
    person_id: int,
    other_id: int,
    kind: RelationKind,
    note: str | None,
    now: datetime,
) -> int:
    '''添加一条六种「认识」关系；对称边归一化成 a < b。'''
    _validate_pair(repo, person_id, other_id)
    if kind not in SELECTABLE_KINDS:
        raise InvalidRelation(f'不能手工添加系统关系：{kind}')
    person_a_id, person_b_id = sorted((person_id, other_id))
    return repo.add_relation(
        Relation(
            person_a_id=person_a_id,
            person_b_id=person_b_id,
            kind=kind,
            note=_clean_note(note),
            created_at=now,
        )
    )


def add_introduction(
    repo: RelationPort,
    *,
    introducer_id: int,
    introduced_id: int,
    note: str | None,
    now: datetime,
) -> int:
    '''记录「introducer 介绍 introduced 给我」；有方向，不转成认识关系。'''
    _validate_pair(repo, introducer_id, introduced_id)
    return repo.add_relation(
        Relation(
            person_a_id=introducer_id,
            person_b_id=introduced_id,
            kind=RelationKind.INTRODUCED,
            note=_clean_note(note),
            created_at=now,
        )
    )


def remove_relation(repo: RelationPort, relation_id: int) -> None:
    repo.delete_relation(relation_id)


def _validate_pair(repo: RelationPort, first: int, second: int) -> None:
    if first == second:
        raise InvalidRelation('不能和自己建立关系')
    if repo.get_person(first) is None:
        raise PersonNotFound(first)
    if repo.get_person(second) is None:
        raise PersonNotFound(second)


def _clean_note(note: str | None) -> str | None:
    text = (note or '').strip()
    return text or None
