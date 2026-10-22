'''记录用例：未确认不入库、重复确认只一条、消歧、字段覆盖。'''

from __future__ import annotations

from datetime import date, datetime

import pytest

from rekindle.app import record
from rekindle.domain.errors import AlreadyConfirmed, CaptureNotFound, MissingName
from rekindle.domain.models import Person
from rekindle.infra.sqlite_repo import SqliteRepo

NOW = datetime(2026, 10, 22, 9, 0)


def test_未确认不产生交往记录(repo: SqliteRepo) -> None:
    record.record(repo, '和张三吃饭', NOW)

    tables = repo.export_all()
    assert tables['interaction'] == []
    assert tables['person'] == []


def test_确认后写入人脉与最近联系时间(repo: SqliteRepo) -> None:
    saved = record.record(repo, '上周和张三在字节工作，他做后端', NOW)
    result = record.confirm(repo, saved.capture_id, now=NOW)

    person = repo.get_person(result.person_id)
    assert person is not None
    assert person.display_name == '张三'
    assert person.company == '字节'
    assert person.role == '后端'
    assert person.last_contact_at == datetime(2026, 10, 15)


def test_重复确认只入库一次(repo: SqliteRepo) -> None:
    saved = record.record(repo, '和张三吃饭', NOW)
    first = record.confirm(repo, saved.capture_id, now=NOW)

    with pytest.raises(AlreadyConfirmed):
        record.confirm(repo, saved.capture_id, now=NOW)

    assert len(repo.export_all()['interaction']) == 1
    capture = repo.get_capture(saved.capture_id)
    assert capture is not None
    assert capture.person_id == first.person_id


def test_同名再次确认复用已有person(repo: SqliteRepo) -> None:
    first = record.confirm(
        repo, record.record(repo, '和张三吃饭', NOW).capture_id, now=NOW
    )
    second = record.confirm(
        repo, record.record(repo, '昨天和张三喝咖啡', NOW).capture_id, now=NOW
    )

    assert second.created_new is False
    assert second.person_id == first.person_id
    assert len(repo.export_all()['person']) == 1


def test_别名命中不新建person(repo: SqliteRepo) -> None:
    first = record.confirm(
        repo, record.record(repo, '和张三吃饭', NOW).capture_id, now=NOW
    )
    repo.add_alias(first.person_id, '张总')

    again = record.record(repo, '认识张总', NOW)
    result = record.confirm(repo, again.capture_id, now=NOW)

    assert result.person_id == first.person_id
    assert len(repo.export_all()['person']) == 1


def test_抽不到姓名且没给name会拒绝(repo: SqliteRepo) -> None:
    saved = record.record(repo, '今天天气不错', NOW)

    with pytest.raises(MissingName):
        record.confirm(repo, saved.capture_id, now=NOW)

    assert repo.export_all()['interaction'] == []


def test_确认时可以覆盖抽取字段(repo: SqliteRepo) -> None:
    saved = record.record(repo, '今天天气不错', NOW)
    result = record.confirm(
        repo,
        saved.capture_id,
        now=NOW,
        name='李四',
        company='腾讯',
        occurred_on=date(2026, 10, 1),
    )

    person = repo.get_person(result.person_id)
    assert person is not None
    assert person.display_name == '李四'
    assert person.company == '腾讯'
    assert person.last_contact_at == datetime(2026, 10, 1)


def test_已导入人脉的罕见姓也能识别(repo: SqliteRepo) -> None:
    repo.add_person(Person(display_name='公皙明'))

    saved = record.record(repo, '和公皙明吃饭', NOW)

    assert saved.parsed.display_name == '公皙明'

    result = record.confirm(repo, saved.capture_id, now=NOW)
    assert result.created_new is False
    assert len(repo.export_all()['person']) == 1


def test_确认不存在的草稿会报错(repo: SqliteRepo) -> None:
    with pytest.raises(CaptureNotFound):
        record.confirm(repo, 999, now=NOW)


def test_丢弃后不能确认(repo: SqliteRepo) -> None:
    saved = record.record(repo, '和张三吃饭', NOW)
    repo.discard_capture(saved.capture_id)

    with pytest.raises(AlreadyConfirmed):
        record.confirm(repo, saved.capture_id, now=NOW)
