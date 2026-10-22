'''编辑用例：改资料、改/删交往记录、归档、快照。'''

from __future__ import annotations

import sqlite3
from datetime import date, datetime

import pytest

from rekindle.app import edit, record
from rekindle.domain.errors import MissingName, SnapshotVersionMismatch
from rekindle.infra.snapshot import (
    create_snapshot,
    list_snapshots,
    restore_snapshot,
)
from rekindle.infra.sqlite_repo import SCHEMA_VERSION, SqliteRepo

NOW = datetime(2026, 10, 22, 9, 0)


def _seed(repo: SqliteRepo) -> int:
    saved = record.record(repo, '上周和张三在字节工作', NOW)
    result = record.confirm(
        repo, saved.capture_id, now=NOW, fields={'wechat': ['wx1']}
    )
    return result.person_id


def test_编辑资料(repo: SqliteRepo) -> None:
    person_id = _seed(repo)

    edit.save_person(
        repo,
        person_id,
        edit.PersonEdit(
            display_name='张三丰',
            role='架构师',
            notes='老同学',
            companies={date(2026, 9, 1): '腾讯', date(2026, 10, 15): '字节'},
            fields={'wechat': ['wx1', 'wx2']},
        ),
    )

    updated = repo.get_person(person_id)
    assert updated is not None
    assert updated.display_name == '张三丰'
    assert updated.role == '架构师'
    assert updated.notes == '老同学'
    assert updated.companies == {
        date(2026, 9, 1): '腾讯',
        date(2026, 10, 15): '字节',
    }
    assert updated.fields == {'wechat': ['wx1', 'wx2']}


def test_姓名不能为空(repo: SqliteRepo) -> None:
    person_id = _seed(repo)

    with pytest.raises(MissingName):
        edit.save_person(
            repo,
            person_id,
            edit.PersonEdit('  ', None, None, {}, {}),
        )


def test_修改交往记录的日期和内容(repo: SqliteRepo) -> None:
    person_id = _seed(repo)
    item = repo.list_interactions(person_id)[0]

    edit.save_interaction(
        repo, item, occurred_on=date(2026, 1, 5), summary='改过的内容'
    )

    updated = repo.list_interactions(person_id)[0]
    assert updated.occurred_at == datetime(2026, 1, 5)
    assert updated.summary == '改过的内容'

    person = repo.get_person(person_id)
    assert person is not None
    assert person.last_contact_at == datetime(2026, 1, 5)


def test_改交往日期不联动公司历史(repo: SqliteRepo) -> None:
    person_id = _seed(repo)
    item = repo.list_interactions(person_id)[0]

    edit.save_interaction(
        repo, item, occurred_on=date(2026, 1, 5), summary='改过的内容'
    )

    person = repo.get_person(person_id)
    assert person is not None
    assert person.companies == {date(2026, 10, 15): '字节'}


def test_删除交往记录后重算最近联系(repo: SqliteRepo) -> None:
    person_id = _seed(repo)
    record.confirm(
        repo,
        record.record(repo, '今天和张三吃饭', NOW).capture_id,
        now=NOW,
    )
    latest = repo.list_interactions(person_id)[0]

    edit.delete_interaction(repo, latest)

    person = repo.get_person(person_id)
    assert person is not None
    assert person.last_contact_at == datetime(2026, 10, 15)


def test_归档后列表不再显示(repo: SqliteRepo) -> None:
    person_id = _seed(repo)

    edit.archive_person(repo, person_id)

    assert repo.list_people() == []
    assert repo.get_person(person_id) is not None


def test_快照只保留最近N份(repo: SqliteRepo) -> None:
    for _ in range(3):
        create_snapshot(repo.path, keep=2)

    files = sorted((repo.path.parent / 'snapshots').glob('rekindle-*.db'))
    assert len(files) == 2

    copy = SqliteRepo(files[-1])
    try:
        assert copy.schema_version == repo.schema_version
    finally:
        copy.close()


def test_快照列表与恢复(repo: SqliteRepo) -> None:
    _seed(repo)
    created = create_snapshot(repo.path)
    record.confirm(
        repo,
        record.record(repo, '今天和李四吃饭', NOW).capture_id,
        now=NOW,
    )
    assert len(repo.list_people()) == 2

    infos = list_snapshots(repo.path)
    assert infos
    assert infos[0].version == repo.schema_version

    safety = restore_snapshot(repo.path, created)
    assert safety.exists()
    assert [p.display_name for p in repo.list_people()] == ['张三']


def test_快照版本不一致会拒绝(repo: SqliteRepo) -> None:
    directory = repo.path.parent / 'snapshots'
    directory.mkdir(exist_ok=True)
    fake = directory / 'rekindle-fake.db'
    conn = sqlite3.connect(fake)
    conn.execute(f'PRAGMA user_version = {SCHEMA_VERSION + 1}')
    conn.close()

    with pytest.raises(SnapshotVersionMismatch):
        restore_snapshot(repo.path, fake)
