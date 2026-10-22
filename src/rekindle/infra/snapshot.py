'''数据库快照：编辑前自动备份，保留最近 N 份。'''

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_KEEP = 10


def snapshot_dir(db_path: Path) -> Path:
    return db_path.parent / 'snapshots'


def create_snapshot(db_path: Path, keep: int = DEFAULT_KEEP) -> Path:
    '''用 SQLite 备份 API 复制一份，避免直接拷 WAL 文件漏数据。'''
    directory = snapshot_dir(db_path)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = directory / f'rekindle-{stamp}.db'
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    _prune(directory, keep)
    return target


def _prune(directory: Path, keep: int) -> None:
    if keep <= 0:
        return
    files = sorted(directory.glob('rekindle-*.db'))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)