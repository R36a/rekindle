'''字段注册表的契约：DDL / 搜索 SQL / CLI / 摘要都必须从它派生。'''

from __future__ import annotations

from pathlib import Path

from rekindle.domain.person_schema import (
    CLI_FIELDS,
    COLUMN_FIELDS,
    CONTACT_FIELDS,
    PERSON_FIELDS,
    SEARCHABLE_FIELDS,
    SUMMARY_FIELDS,
    Storage,
)
from rekindle.infra.sqlite_repo import SqliteRepo


def test_key不重复() -> None:
    keys = [field.key for field in PERSON_FIELDS]

    assert len(keys) == len(set(keys))


def test_生成的DDL与真实表结构一致(tmp_path: Path) -> None:
    # 生成器只要和真实表有一列/一个约束不一致，这里就会炸。
    repo = SqliteRepo(tmp_path / 'schema.db')
    try:
        actual = [
            (row['name'], row['type'], row['notnull'], row['dflt_value'], row['pk'])
            for row in repo._conn.execute('PRAGMA table_info(person)')
        ]
    finally:
        repo.close()

    expected = [
        (field.key, field.sql_type, int(field.not_null), field.sql_default, int(field.primary_key))
        for field in COLUMN_FIELDS
    ]
    assert actual == expected


def test_搜索SQL覆盖所有searchable字段() -> None:
    from rekindle.infra.sqlite_repo import _SEARCH_SQL

    for field in SEARCHABLE_FIELDS:
        if field.storage is Storage.COLUMN:
            assert f'p.{field.key}' in _SEARCH_SQL
    for field in CONTACT_FIELDS:
        assert f"'{field.key}'" in _SEARCH_SQL
    assert 'person_company' in _SEARCH_SQL


def test_CLI参数覆盖可写字段() -> None:
    flags = {field.flag for field in CLI_FIELDS}

    assert {'name', 'company', 'role'} <= flags
    assert {field.key for field in CONTACT_FIELDS} <= flags


def test_摘要按注册表顺序输出() -> None:
    keys = [field.key for field in SUMMARY_FIELDS]

    assert keys[:3] == ['display_name', 'company', 'role']
    assert set(field.key for field in CONTACT_FIELDS) <= set(keys)
