'''关系类型顺序与关系边的领域约束。'''

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from rekindle.domain.models import Relation
from rekindle.domain.relations import (
    RELATION_KINDS,
    SELECTABLE_KINDS,
    SELECTABLE_LABELS,
    RelationKind,
    label_of,
    rank_of,
)

NOW = datetime(2026, 10, 24, 9, 0)


def test_关系类型按浅到深排列() -> None:
    assert SELECTABLE_LABELS == ('陌生人', '客户', '同事', '同学', '朋友', '亲戚')
    assert [spec.rank for spec in RELATION_KINDS] == [0, 1, 2, 3, 4, 5]
    assert RelationKind.INTRODUCED not in SELECTABLE_KINDS


def test_关系标签与排序() -> None:
    assert label_of(RelationKind.FRIEND) == '朋友'
    assert rank_of(RelationKind.STRANGER) < rank_of(RelationKind.RELATIVE)


def test_对称关系必须a小于b() -> None:
    with pytest.raises(ValidationError, match='person_a_id < person_b_id'):
        Relation(
            person_a_id=2,
            person_b_id=1,
            kind=RelationKind.FRIEND,
            created_at=NOW,
        )


def test_不能和自己建立关系() -> None:
    with pytest.raises(ValidationError, match='不能和自己'):
        Relation(
            person_a_id=1,
            person_b_id=1,
            kind=RelationKind.FRIEND,
            created_at=NOW,
        )


def test_介绍关系保留方向() -> None:
    relation = Relation(
        person_a_id=2,
        person_b_id=1,
        kind=RelationKind.INTRODUCED,
        created_at=NOW,
    )
    assert relation.person_a_id == 2
    assert relation.person_b_id == 1
