'''JSON 备份：导出 → 空库导入后逐字段相等。'''

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from rekindle.app import backup, record
from rekindle.domain.errors import BackupFormatError, ImportTargetNotEmpty
from rekindle.infra.sqlite_repo import SqliteRepo

NOW = datetime(2026, 10, 22, 9, 0)


def test_导出导入往返一致(repo: SqliteRepo, tmp_path: Path) -> None:
    saved = record.record(repo, '上周和张三在字节工作', NOW)
    result = record.confirm(
        repo, saved.capture_id, now=NOW, fields={'wechat': ['wx1']}
    )
    repo.add_alias(result.person_id, '张总')

    out = backup.export_to(repo, tmp_path / 'backup.json', NOW)

    restored = SqliteRepo(tmp_path / 'restored.db')
    try:
        assert backup.import_from(restored, out) == 1
        # 逐表逐字段比较：这是「导出能恢复」的唯一硬证据。
        assert restored.export_all() == repo.export_all()
    finally:
        restored.close()


def test_导入到非空库被拒绝(repo: SqliteRepo, tmp_path: Path) -> None:
    saved = record.record(repo, '和张三吃饭', NOW)
    record.confirm(repo, saved.capture_id, now=NOW)
    out = backup.export_to(repo, tmp_path / 'backup.json', NOW)

    with pytest.raises(ImportTargetNotEmpty):
        backup.import_from(repo, out)


def test_可以导入v3旧备份(repo: SqliteRepo, tmp_path: Path) -> None:
    path = tmp_path / 'v3.json'
    payload = {
        'format': 'rekindle-backup',
        'version': 3,
        'tables': {
            'person': [
                {
                    'id': 1,
                    'display_name': '张三',
                    'pinyin': '',
                    'initials': '',
                    'role': None,
                    'notes': None,
                    'last_contact_at': None,
                    'archived': 0,
                }
            ]
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    assert backup.import_from(repo, path) == 1
    assert repo.list_people()[0].display_name == '张三'

def test_不是本项目的文件会被拒绝(repo: SqliteRepo, tmp_path: Path) -> None:
    path = tmp_path / 'other.json'
    path.write_text('{"hello": 1}', encoding='utf-8')

    with pytest.raises(BackupFormatError, match='不是 rekindle'):
        backup.import_from(repo, path)
