'''CLI 端到端：命令能串起来、错误有中文提示与退出码。'''

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from rekindle.infra.sqlite_repo import SqliteRepo
from rekindle.interfaces.cli import main


def test_记住确认再列出(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')

    assert main(['remember', '上周和张三在字节工作', '--db', db]) == 0
    out = capsys.readouterr().out
    assert 'capture #1' in out
    assert '张三' in out

    assert main(['confirm', '1', '--db', db]) == 0
    out = capsys.readouterr().out
    assert '已确认' in out
    assert '张三' in out

    assert main(['list', '--db', db]) == 0
    assert '张三' in capsys.readouterr().out


def test_按公司搜索(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')
    main(['remember', '和张三在字节工作', '--db', db])
    main(['confirm', '1', '--db', db])
    capsys.readouterr()

    assert main(['list', '-q', '字节', '--db', db]) == 0
    assert '张三' in capsys.readouterr().out

    assert main(['list', '-q', '腾讯', '--db', db]) == 0
    assert '没有匹配' in capsys.readouterr().out


def test_重复确认返回退出码1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')
    main(['remember', '和张三吃饭', '--db', db])
    main(['confirm', '1', '--db', db])
    capsys.readouterr()

    assert main(['confirm', '1', '--db', db]) == 1
    assert '错误' in capsys.readouterr().err


def test_没有姓名时提示并返回1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')
    main(['remember', '今天天气不错', '--db', db])
    capsys.readouterr()

    assert main(['confirm', '1', '--db', db]) == 1
    assert '--name' in capsys.readouterr().err


def test_导出后导入空库(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')
    backup_path = str(tmp_path / 'backup.json')
    main(['remember', '和张三吃饭', '--db', db])
    main(['confirm', '1', '--db', db])
    assert main(['export', backup_path, '--db', db]) == 0
    capsys.readouterr()

    other = str(tmp_path / 'other.db')
    assert main(['import', backup_path, '--db', other]) == 0
    assert '已导入 1 位联系人' in capsys.readouterr().out

    assert main(['list', '--db', other]) == 0
    assert '张三' in capsys.readouterr().out


def test_别名可以被搜到(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')
    main(['remember', '和张三吃饭', '--db', db])
    main(['confirm', '1', '--db', db])
    assert main(['alias', '1', '张总', '--db', db]) == 0
    capsys.readouterr()

    assert main(['list', '-q', '张总', '--db', db]) == 0
    assert '张三' in capsys.readouterr().out


def test_丢弃草稿(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')
    main(['remember', '和张三吃饭', '--db', db])

    assert main(['discard', '1', '--db', db]) == 0
    assert '已丢弃' in capsys.readouterr().out


def test_空参数打印帮助(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert 'rekindle' in capsys.readouterr().out


def test_when支持相对日期(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')
    main(['remember', '和张三吃饭', '--db', db])
    assert main(['confirm', '1', '--when', '昨天', '--db', db]) == 0
    capsys.readouterr()

    with SqliteRepo(db) as repo:
        people = repo.list_people()
    assert people[0].last_contact_at is not None
    assert people[0].last_contact_at.date() == date.today() - timedelta(days=1)


def test_联系方式可以通过命令行写入(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(tmp_path / 'cli.db')
    main(['remember', '和张三吃饭', '--db', db])
    assert main(
        ['confirm', '1', '--wechat', 'wx123', '--email', 'a@b.com', '--db', db]
    ) == 0
    capsys.readouterr()

    assert main(['show', '1', '--db', db]) == 0
    out = capsys.readouterr().out
    assert '微信：wx123' in out
    assert '邮箱：a@b.com' in out


def test_add_不写句子直接入库(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(tmp_path / 'cli.db')
    assert main(
        ['add', '--name', '张三', '--company', '字节', '--wechat', 'wx123', '--db', db]
    ) == 0
    capsys.readouterr()

    assert main(['show', '1', '--db', db]) == 0
    out = capsys.readouterr().out
    assert '微信：wx123' in out
    assert '用户输入了：姓名：张三' in out


def test_联系方式可以重复添加(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(tmp_path / 'cli.db')
    main(['add', '--name', '张三', '--wechat', 'wx1', '--db', db])
    main(['add', '--name', '张三', '--wechat', 'wx2', '--db', db])
    main(['add', '--name', '张三', '--wechat', 'wx3', '--wechat', 'wx4', '--db', db])
    capsys.readouterr()

    assert main(['show', '1', '--db', db]) == 0
    assert '微信：wx1、wx2、wx3、wx4' in capsys.readouterr().out


def test_归档和快照(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / 'cli.db')
    main(['add', '--name', '张三', '--db', db])

    assert main(['archive', '1', '--db', db]) == 0
    capsys.readouterr()
    assert main(['list', '--db', db]) == 0
    assert '没有匹配' in capsys.readouterr().out

    assert main(['snapshot', '--db', db]) == 0
    assert '已备份' in capsys.readouterr().out
