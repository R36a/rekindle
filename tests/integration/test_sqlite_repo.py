'''存储层：迁移幂等、别名唯一、唯一约束靠数据库兜底。'''

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from rekindle.domain.errors import AlreadyConfirmed
from rekindle.domain.models import ExtractedFields, Interaction, Person
from rekindle.infra.sqlite_repo import SCHEMA_VERSION, SqliteRepo

NOW = datetime(2026, 10, 22, 9, 0)


def test_重复打开同一库不会重复建表(tmp_path: Path) -> None:
    path = tmp_path / 'migrate.db'
    first = SqliteRepo(path)
    first.close()

    reopened = SqliteRepo(path)
    try:
        assert reopened.schema_version == SCHEMA_VERSION
    finally:
        reopened.close()


def test_同一人同一称呼只会有一条别名(repo: SqliteRepo) -> None:
    person_id = repo.add_person(Person(display_name='张三'))
    repo.add_alias(person_id, '张总')
    repo.add_alias(person_id, '张 总')

    assert len(repo.export_all()['alias']) == 1


def test_同一capture不能写两条interaction(repo: SqliteRepo) -> None:
    person_id = repo.add_person(Person(display_name='张三'))
    capture_id = repo.add_capture('和张三吃饭', NOW, ExtractedFields(display_name='张三'))
    interaction = Interaction(
        person_id=person_id,
        capture_id=capture_id,
        occurred_at=NOW,
        summary='和张三吃饭',
        created_at=NOW,
    )
    repo.add_interaction(interaction)

    with pytest.raises(AlreadyConfirmed):
        repo.add_interaction(interaction.model_copy(update={'id': None}))
