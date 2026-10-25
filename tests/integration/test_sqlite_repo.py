'''存储层：迁移幂等、别名唯一、唯一约束靠数据库兜底。'''

from __future__ import annotations

import sqlite3
from datetime import date, datetime
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


def test_v6库升级保留属性字段并删掉注册表(tmp_path: Path) -> None:
    path = tmp_path / 'v6.db'
    SqliteRepo(path).close()  # 先得到当前版本的 person 等基础表

    # 还原 v6 形状（field 表 + 外键 + 两列拼音），模拟已发布的 v0.1.0 数据库。
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            '''
            ALTER TABLE person ADD COLUMN pinyin TEXT NOT NULL DEFAULT '';
            ALTER TABLE person ADD COLUMN initials TEXT NOT NULL DEFAULT '';
            DROP TABLE person_field;
            CREATE TABLE field (
                key         TEXT PRIMARY KEY,
                label       TEXT NOT NULL,
                field_type  TEXT NOT NULL DEFAULT 'text',
                description TEXT NOT NULL DEFAULT '',
                builtin     INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE person_field (
                person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
                field_key TEXT    NOT NULL REFERENCES field(key) ON DELETE CASCADE,
                value     TEXT    NOT NULL,
                PRIMARY KEY (person_id, field_key, value)
            );
            CREATE INDEX ix_person_field_value ON person_field(value);
            INSERT INTO person (id, display_name, pinyin) VALUES (1, '张三', 'zhangsan');
            INSERT INTO field (key, label) VALUES ('wechat', '微信');
            INSERT INTO person_field (person_id, field_key, value)
                VALUES (1, 'wechat', 'wx1');
            PRAGMA user_version = 6;
            '''
        )
        conn.commit()
    finally:
        conn.close()

    migrated = SqliteRepo(path)
    try:
        assert migrated.schema_version == SCHEMA_VERSION
        person = migrated.get_person(1)
        assert person is not None
        assert person.fields == {'wechat': ['wx1']}
    finally:
        migrated.close()

    check = sqlite3.connect(path)
    try:
        tables = {
            str(row[0])
            for row in check.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        columns = {
            str(row[1]) for row in check.execute('PRAGMA table_info(person)')
        }
    finally:
        check.close()
    assert 'field' not in tables
    assert 'pinyin' not in columns and 'initials' not in columns


def test_v7库升级删掉拼音列但保住数据(tmp_path: Path) -> None:
    path = tmp_path / 'v7.db'
    SqliteRepo(path).close()

    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            '''
            ALTER TABLE person ADD COLUMN pinyin TEXT NOT NULL DEFAULT '';
            ALTER TABLE person ADD COLUMN initials TEXT NOT NULL DEFAULT '';
            INSERT INTO person (id, display_name, pinyin, initials)
                VALUES (7, '李四', 'lisi', 'ls');
            INSERT INTO person_company (person_id, on_date, company)
                VALUES (7, '2026-10-20', '腾讯');
            PRAGMA user_version = 7;
            '''
        )
        conn.commit()
    finally:
        conn.close()

    migrated = SqliteRepo(path)
    try:
        assert migrated.schema_version == SCHEMA_VERSION
        person = migrated.get_person(7)
        assert person is not None
        assert person.display_name == '李四'
        assert person.companies == {date(2026, 10, 20): '腾讯'}
    finally:
        migrated.close()

    check = sqlite3.connect(path)
    try:
        columns = [str(row[1]) for row in check.execute('PRAGMA table_info(person)')]
    finally:
        check.close()
    assert columns == [
        'id', 'display_name', 'role', 'notes', 'last_contact_at', 'archived'
    ]


def test_atomic可嵌套且外层回滚(repo: SqliteRepo) -> None:
    # 故意嵌套两层：验证内层复用外层、外层失败时整体回滚（不能合并成一个 with）。
    with pytest.raises(RuntimeError):  # noqa: SIM117
        with repo.atomic():
            repo.add_person(Person(display_name='张三'))
            with repo.atomic():
                repo.add_person(Person(display_name='李四'))
            raise RuntimeError('boom')

    assert repo.export_all()['person'] == []
