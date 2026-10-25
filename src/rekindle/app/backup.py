'''JSON 备份：单文件导出 / 导入（开发文档 §4.3，JSON 是权威格式）。

导入只写空库：原型阶段宁可直接拒绝，也不做「合并冲突」这种容易丢数据的活。
'''

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rekindle.app.ports import Repo
from rekindle.domain.errors import BackupFormatError

EXPORT_FORMAT = 'rekindle-backup'
# v4 增加 person_relation；仍接受 v3（没有关系表）的旧备份。
EXPORT_VERSION = 4
SUPPORTED_VERSIONS = (3, EXPORT_VERSION)


def export_to(repo: Repo, path: str | Path, now: datetime) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'format': EXPORT_FORMAT,
        'version': EXPORT_VERSION,
        'exported_at': now.isoformat(),
        'tables': repo.export_all(),
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return target


def import_from(repo: Repo, path: str | Path) -> int:
    '''返回导入的 person 条数（便于 CLI 报告结果）。'''
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('format') != EXPORT_FORMAT:
        raise BackupFormatError('不是 rekindle 导出的 JSON 文件')
    if data.get('version') not in SUPPORTED_VERSIONS:
        raise BackupFormatError(f'不支持的备份版本：{data.get("version")}')
    tables = data.get('tables')
    if not isinstance(tables, dict):
        raise BackupFormatError('备份文件缺少 tables')
    repo.import_all(tables)
    people = tables.get('person', [])
    return len(people) if isinstance(people, list) else 0
