'''人与人之间的关系类型。

六种「认识」关系按社交距离从浅到深排列；`introduced` 是系统类型，
表示「谁介绍谁」，不参与下拉选择，也不参与深浅排序。
'''

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RelationKind(StrEnum):
    '''关系类型 key；数据库存 key，界面显示 label。'''

    STRANGER = 'stranger'
    CLIENT = 'client'
    COLLEAGUE = 'colleague'
    CLASSMATE = 'classmate'
    FRIEND = 'friend'
    RELATIVE = 'relative'
    INTRODUCED = 'introduced'  # 系统类型：a 介绍 b


@dataclass(frozen=True)
class RelationSpec:
    kind: RelationKind
    label: str
    rank: int


# 顺序即 UI 下拉顺序：浅 → 深。
RELATION_KINDS: tuple[RelationSpec, ...] = (
    RelationSpec(RelationKind.STRANGER, '陌生人', 0),
    RelationSpec(RelationKind.CLIENT, '客户', 1),
    RelationSpec(RelationKind.COLLEAGUE, '同事', 2),
    RelationSpec(RelationKind.CLASSMATE, '同学', 3),
    RelationSpec(RelationKind.FRIEND, '朋友', 4),
    RelationSpec(RelationKind.RELATIVE, '亲戚', 5),
)

SELECTABLE_KINDS: tuple[RelationKind, ...] = tuple(
    spec.kind for spec in RELATION_KINDS
)
SELECTABLE_LABELS: tuple[str, ...] = tuple(spec.label for spec in RELATION_KINDS)
KIND_BY_LABEL: dict[str, RelationKind] = {
    spec.label: spec.kind for spec in RELATION_KINDS
}
RELATION_LABELS: dict[str, str] = {
    spec.kind.value: spec.label for spec in RELATION_KINDS
}
RELATION_LABELS[RelationKind.INTRODUCED.value] = '介绍'
RELATION_RANK: dict[str, int] = {
    spec.kind.value: spec.rank for spec in RELATION_KINDS
}
RELATION_RANK[RelationKind.INTRODUCED.value] = 99


def label_of(kind: RelationKind) -> str:
    return RELATION_LABELS[kind.value]


def rank_of(kind: RelationKind) -> int:
    return RELATION_RANK[kind.value]
