'''记录用例：未确认不入库、重复确认只一条、消歧、字段覆盖。'''

from __future__ import annotations

from datetime import date, datetime

import pytest

from rekindle.app import record
from rekindle.domain.errors import (
    AlreadyConfirmed,
    CaptureNotFound,
    EmptyCapture,
    MissingName,
    NameTooLong,
)
from rekindle.domain.models import Person
from rekindle.domain.text import NAME_MAX_LENGTH
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
    assert person.companies == {date(2026, 10, 15): '字节'}
    assert person.current_company == '字节'
    assert person.role == '后端'
    assert person.last_contact_at == datetime(2026, 10, 15)


def test_确认会清洗公司与职位的首尾空白(repo: SqliteRepo) -> None:
    saved = record.record(repo, '和张三吃饭', NOW)
    result = record.confirm(
        repo, saved.capture_id, now=NOW, company='  字节  ', role=' 后端 '
    )

    person = repo.get_person(result.person_id)
    assert person is not None
    assert person.current_company == '字节'
    assert person.role == '后端'


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
        display_name='李四',
        company='腾讯',
        occurred_on=date(2026, 10, 1),
    )

    person = repo.get_person(result.person_id)
    assert person is not None
    assert person.display_name == '李四'
    assert person.companies == {date(2026, 10, 1): '腾讯'}
    assert person.last_contact_at == datetime(2026, 10, 1)


def test_已导入人脉的罕见姓也能识别(repo: SqliteRepo) -> None:
    repo.add_person(Person(display_name='公皙明'))

    saved = record.record(repo, '和公皙明吃饭', NOW)

    assert saved.parsed.display_name == '公皙明'

    result = record.confirm(repo, saved.capture_id, now=NOW)
    assert result.created_new is False
    assert len(repo.export_all()['person']) == 1


def test_日期字段默认今天(repo: SqliteRepo) -> None:
    saved = record.record(repo, '和张三吃饭', NOW)

    assert saved.parsed.occurred_at == date(2026, 10, 22)

    result = record.confirm(repo, saved.capture_id, now=NOW)
    person = repo.get_person(result.person_id)
    assert person is not None
    assert person.last_contact_at == datetime(2026, 10, 22)


def test_同一人不同时间的两家公司都会保留(repo: SqliteRepo) -> None:
    first = record.confirm(
        repo, record.record(repo, '上周和张三在字节工作', NOW).capture_id, now=NOW
    )
    second = record.confirm(
        repo, record.record(repo, '今天和张三在腾讯工作', NOW).capture_id, now=NOW
    )

    assert second.person_id == first.person_id
    person = repo.get_person(first.person_id)
    assert person is not None
    assert person.companies == {
        date(2026, 10, 15): '字节',
        date(2026, 10, 22): '腾讯',
    }
    assert person.current_company == '腾讯'


def test_确认时保存联系方式(repo: SqliteRepo) -> None:
    saved = record.record(repo, '和张三吃饭', NOW)
    result = record.confirm(
        repo,
        saved.capture_id,
        now=NOW,
        fields={
            'wechat': ['zhangsan_wx'],
            'qq': ['12345'],
            'email': ['zhangsan@example.com'],
            'phone': ['13800000000'],
        },
    )

    person = repo.get_person(result.person_id)
    assert person is not None
    assert person.fields == {
        'wechat': ['zhangsan_wx'],
        'qq': ['12345'],
        'email': ['zhangsan@example.com'],
        'phone': ['13800000000'],
    }
    assert len(repo.list_people('zhangsan_wx')) == 1


def test_空白联系方式不会覆盖已有(repo: SqliteRepo) -> None:
    first = record.confirm(
        repo,
        record.record(repo, '和张三吃饭', NOW).capture_id,
        now=NOW,
        fields={'wechat': ['wx1']},
    )
    record.confirm(
        repo,
        record.record(repo, '昨天和张三吃饭', NOW).capture_id,
        now=NOW,
    )

    person = repo.get_person(first.person_id)
    assert person is not None
    assert person.fields == {'wechat': ['wx1']}


def test_不写句子也能入库(repo: SqliteRepo) -> None:
    result = record.manual(
        repo,
        now=NOW,
        display_name='张三',
        company='字节',
        role='后端',
        fields={'wechat': ['wx1']},
    )

    person = repo.get_person(result.person_id)
    assert person is not None
    assert person.companies == {date(2026, 10, 22): '字节'}
    assert person.fields == {'wechat': ['wx1']}

    interactions = repo.list_interactions(result.person_id)
    assert interactions[0].summary == (
        '用户输入了：姓名：张三，日期：2026-10-22，公司：字节，职位：后端，微信：wx1'
    )


def test_手动入库必须有姓名(repo: SqliteRepo) -> None:
    with pytest.raises(MissingName):
        record.manual(repo, now=NOW, display_name='   ')

    assert repo.export_all()['interaction'] == []


def test_再次添加联系方式会追加并去重(repo: SqliteRepo) -> None:
    first = record.confirm(
        repo,
        record.record(repo, '和张三吃饭', NOW).capture_id,
        now=NOW,
        fields={'wechat': ['wx1']},
    )
    record.confirm(
        repo,
        record.record(repo, '昨天和张三吃饭', NOW).capture_id,
        now=NOW,
        fields={'wechat': ['wx2', 'wx1']},
    )

    person = repo.get_person(first.person_id)
    assert person is not None
    assert person.fields == {'wechat': ['wx1', 'wx2']}


def test_确认不存在的草稿会报错(repo: SqliteRepo) -> None:
    with pytest.raises(CaptureNotFound):
        record.confirm(repo, 999, now=NOW)


def test_丢弃后不能确认(repo: SqliteRepo) -> None:
    saved = record.record(repo, '和张三吃饭', NOW)
    repo.discard_capture(saved.capture_id)

    with pytest.raises(AlreadyConfirmed):
        record.confirm(repo, saved.capture_id, now=NOW)


def test_补录更早的历史记录不会让最近联系回退(repo: SqliteRepo) -> None:
    first = record.manual(repo, now=NOW, display_name='张三', occurred_on=date(2026, 10, 21))
    record.manual(repo, now=NOW, display_name='李四', occurred_on=date(2026, 10, 20))

    # 再补一条更早的历史记录：最近联系仍是 10-21，列表顺序不能被打乱。
    record.manual(repo, now=NOW, display_name='张三', occurred_on=date(2026, 1, 1))

    person = repo.get_person(first.person_id)
    assert person is not None
    assert person.last_contact_at == datetime(2026, 10, 21)
    assert [item.display_name for item in repo.list_people()] == ['张三', '李四']


def test_确认补录更早的历史记录不会让最近联系回退(repo: SqliteRepo) -> None:
    first = record.confirm(
        repo,
        record.record(repo, '和张三吃饭', NOW).capture_id,
        now=NOW,
        occurred_on=date(2026, 10, 21),
    )
    record.confirm(
        repo,
        record.record(repo, '和李四吃饭', NOW).capture_id,
        now=NOW,
        occurred_on=date(2026, 10, 20),
    )
    record.confirm(
        repo,
        record.record(repo, '上个月和张三吃饭', NOW).capture_id,
        now=NOW,
        occurred_on=date(2026, 1, 1),
    )

    person = repo.get_person(first.person_id)
    assert person is not None
    assert person.last_contact_at == datetime(2026, 10, 21)


def test_姓名超长会被拒绝(repo: SqliteRepo) -> None:
    with pytest.raises(NameTooLong):
        record.manual(repo, now=NOW, display_name='张' * (NAME_MAX_LENGTH + 1))

    assert repo.export_all()['person'] == []


def test_空白原话不会被存成草稿(repo: SqliteRepo) -> None:
    with pytest.raises(EmptyCapture):
        record.record(repo, '   ', NOW)

    assert repo.export_all()['capture'] == []
