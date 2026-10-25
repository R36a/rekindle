'''关系边：对称归一化、唯一约束、介绍方向、备份往返。'''

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from rekindle.app import backup
from rekindle.app import relations as relation_uc
from rekindle.domain.errors import (
    InvalidRelation,
    PersonNotFound,
    RelationExists,
    RelationNotFound,
)
from rekindle.domain.models import Person
from rekindle.domain.relations import RelationKind
from rekindle.infra.sqlite_repo import SqliteRepo

NOW = datetime(2026, 10, 24, 9, 0)


def _person(repo: SqliteRepo, name: str) -> int:
    return repo.add_person(Person(display_name=name))


def test_添加认识关系双方都能查到(repo: SqliteRepo) -> None:
    zhang = _person(repo, '张三')
    li = _person(repo, '李四')

    relation_uc.add_relation(
        repo,
        person_id=zhang,
        other_id=li,
        kind=RelationKind.FRIEND,
        note='大学同学',
        now=NOW,
    )

    for person_id in (zhang, li):
        relations = repo.list_relations(person_id)
        assert len(relations) == 1
        assert relations[0].kind == RelationKind.FRIEND
        assert relations[0].note == '大学同学'


def test_对称关系只存一份(repo: SqliteRepo) -> None:
    zhang = _person(repo, '张三')
    li = _person(repo, '李四')
    relation_uc.add_relation(
        repo,
        person_id=li,
        other_id=zhang,
        kind=RelationKind.COLLEAGUE,
        note=None,
        now=NOW,
    )
    with pytest.raises(RelationExists):
        relation_uc.add_relation(
            repo,
            person_id=zhang,
            other_id=li,
            kind=RelationKind.COLLEAGUE,
            note=None,
            now=NOW,
        )

    rows = repo.export_all()['person_relation']
    assert len(rows) == 1
    assert int(rows[0]['person_a_id']) < int(rows[0]['person_b_id'])


def test_介绍关系保留方向且不自动变成认识关系(repo: SqliteRepo) -> None:
    zhang = _person(repo, '张三')
    li = _person(repo, '李四')

    relation_uc.add_introduction(
        repo,
        introducer_id=zhang,
        introduced_id=li,
        note=None,
        now=NOW,
    )

    introduced = repo.list_relations(zhang)
    assert len(introduced) == 1
    assert introduced[0].kind == RelationKind.INTRODUCED
    assert introduced[0].person_a_id == zhang
    assert introduced[0].person_b_id == li
    assert [
        relation
        for relation in repo.list_relations(zhang)
        if relation.kind != RelationKind.INTRODUCED
    ] == []


def test_介绍关系只能记录一次(repo: SqliteRepo) -> None:
    zhang = _person(repo, '张三')
    li = _person(repo, '李四')
    relation_uc.add_introduction(
        repo,
        introducer_id=zhang,
        introduced_id=li,
        note=None,
        now=NOW,
    )

    with pytest.raises(RelationExists):
        relation_uc.add_introduction(
            repo,
            introducer_id=zhang,
            introduced_id=li,
            note=None,
            now=NOW,
        )


def test_不能和自己建立关系(repo: SqliteRepo) -> None:
    zhang = _person(repo, '张三')

    with pytest.raises(InvalidRelation):
        relation_uc.add_relation(
            repo,
            person_id=zhang,
            other_id=zhang,
            kind=RelationKind.FRIEND,
            note=None,
            now=NOW,
        )
    with pytest.raises(InvalidRelation):
        relation_uc.add_relation(
            repo,
            person_id=zhang,
            other_id=_person(repo, '李四'),
            kind=RelationKind.INTRODUCED,
            note=None,
            now=NOW,
        )


def test_两端必须存在(repo: SqliteRepo) -> None:
    zhang = _person(repo, '张三')

    with pytest.raises(PersonNotFound):
        relation_uc.add_relation(
            repo,
            person_id=zhang,
            other_id=999,
            kind=RelationKind.FRIEND,
            note=None,
            now=NOW,
        )


def test_移除关系(repo: SqliteRepo) -> None:
    zhang = _person(repo, '张三')
    li = _person(repo, '李四')
    relation_id = relation_uc.add_relation(
        repo,
        person_id=zhang,
        other_id=li,
        kind=RelationKind.FRIEND,
        note=None,
        now=NOW,
    )

    relation_uc.remove_relation(repo, relation_id)

    assert repo.list_relations(zhang) == []
    with pytest.raises(RelationNotFound):
        relation_uc.remove_relation(repo, relation_id)


def test_归档后关系仍在(repo: SqliteRepo) -> None:
    zhang = _person(repo, '张三')
    li = _person(repo, '李四')
    relation_uc.add_relation(
        repo,
        person_id=zhang,
        other_id=li,
        kind=RelationKind.FRIEND,
        note=None,
        now=NOW,
    )

    repo.archive_person(zhang)

    assert len(repo.list_relations(zhang)) == 1


def test_导出导入包含关系(repo: SqliteRepo, tmp_path: Path) -> None:
    zhang = _person(repo, '张三')
    li = _person(repo, '李四')
    relation_uc.add_relation(
        repo,
        person_id=zhang,
        other_id=li,
        kind=RelationKind.FRIEND,
        note=None,
        now=NOW,
    )
    relation_uc.add_introduction(
        repo,
        introducer_id=zhang,
        introduced_id=li,
        note=None,
        now=NOW,
    )
    out = backup.export_to(repo, tmp_path / 'backup.json', NOW)

    restored = SqliteRepo(tmp_path / 'restored.db')
    try:
        assert backup.import_from(restored, out) == 2
        assert restored.export_all() == repo.export_all()
        assert len(restored.list_relations(zhang)) == 2
    finally:
        restored.close()


def test_数据库CHECK覆盖全部关系类型(repo: SqliteRepo) -> None:
    # 「类型清单」还有第三份：DDL 里的 CHECK。加了类型忘了改它，插入会被数据库拒绝。
    sql = repo._conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'person_relation'"
    ).fetchone()[0]
    for kind in RelationKind:
        assert f"'{kind.value}'" in sql
