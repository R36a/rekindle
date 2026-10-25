'''数据库快照：自动备份、列表与恢复。'''

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rekindle.domain.errors import SnapshotVersionMismatch
from rekindle.domain.models import DEFAULT_SNAPSHOT_KEEP
from rekindle.infra.sqlite_repo import SCHEMA_VERSION


@dataclass(frozen=True)
class SnapshotInfo:
    path: Path
    created_at: datetime
    size: int
    version: int


def snapshot_dir(db_path: Path) -> Path:
    return db_path.parent / 'snapshots'


def create_snapshot(db_path: Path, keep: int = DEFAULT_SNAPSHOT_KEEP) -> Path:
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


def list_snapshots(db_path: Path) -> list[SnapshotInfo]:
    '''按时间倒序返回快照。'''
    directory = snapshot_dir(db_path)
    if not directory.exists():
        return []
    infos: list[SnapshotInfo] = []
    for path in directory.glob('rekindle-*.db'):
        stat = path.stat()
        try:
            version = snapshot_version(path)
        except sqlite3.Error:
            version = -1
        infos.append(
            SnapshotInfo(
                path=path,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                size=stat.st_size,
                version=version,
            )
        )
    return sorted(infos, key=lambda item: item.created_at, reverse=True)


def snapshot_version(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        row = conn.execute('PRAGMA user_version').fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def restore_snapshot(db_path: Path, snapshot_path: Path) -> Path:
    '''恢复快照，返回恢复前自动保存的「后悔药」快照。'''
    version = snapshot_version(snapshot_path)
    if version != SCHEMA_VERSION:
        raise SnapshotVersionMismatch(version, SCHEMA_VERSION)

    # keep=0 本次不清理：避免把正在恢复的旧快照顺手删掉。
    safety = create_snapshot(db_path, keep=0)
    source = sqlite3.connect(snapshot_path)
    dest = sqlite3.connect(db_path)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return safety


def _prune(directory: Path, keep: int) -> None:
    if keep <= 0:
        return
    files = sorted(directory.glob('rekindle-*.db'))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)