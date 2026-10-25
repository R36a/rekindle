'''人与人之间的关系类型：一张表，其余全是它的投影。

六种「认识」关系按社交距离从浅到深排列；`introduced` 是系统类型（谁介绍谁），
不参与下拉选择，也不参与深浅排序。

以前还有 RELATION_LABELS / RELATION_RANK 两个平行字典，推导完再按下标补一行
（`[INTRODUCED] = '介绍'` / `= 99`），等于同一份数据写两遍；现在只有 RELATIONS。
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
    '''一种关系的展示信息。key 就是 RELATIONS 的键，不在这里重复存。'''

    label: str
    rank: int


# 顺序即 UI 下拉顺序：浅 → 深；系统类型排在最后，rank 用 99 表示「不参与排序」。
RELATIONS: dict[RelationKind, RelationSpec] = {
    RelationKind.STRANGER: RelationSpec('陌生人', 0),
    RelationKind.CLIENT: RelationSpec('客户', 1),
    RelationKind.COLLEAGUE: RelationSpec('同事', 2),
    RelationKind.CLASSMATE: RelationSpec('同学', 3),
    RelationKind.FRIEND: RelationSpec('朋友', 4),
    RelationKind.RELATIVE: RelationSpec('亲戚', 5),
    RelationKind.INTRODUCED: RelationSpec('介绍', 99),
}


def label_of(kind: RelationKind) -> str:
    return RELATIONS[kind].label


def rank_of(kind: RelationKind) -> int:
    return RELATIONS[kind].rank


# 下面三个都是同一张表的投影，不新增事实。
SELECTABLE_KINDS: tuple[RelationKind, ...] = tuple(
    kind for kind in RELATIONS if kind is not RelationKind.INTRODUCED
)
SELECTABLE_LABELS: tuple[str, ...] = tuple(
    label_of(kind) for kind in SELECTABLE_KINDS
)
KIND_BY_LABEL: dict[str, RelationKind] = {
    label_of(kind): kind for kind in SELECTABLE_KINDS
}

