'''数据库快照：自动备份、列表与恢复。'''

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rekindle.domain.errors import SnapshotVersionMismatch
from rekindle.infra.sqlite_repo import SCHEMA_VERSION, SqliteRepo, can_upgrade_from

# 快照保留份数：只有一个消费者（create_snapshot），不再跨层共用。
DEFAULT_SNAPSHOT_KEEP = 10


def _copy_database(source: Path, target: Path) -> None:
    '''用 SQLite 备份 API 复制：直接拷文件会漏掉 WAL 里的数据。'''
    source_conn = sqlite3.connect(source)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()


@dataclass(frozen=True)
class SnapshotInfo:
    path: Path
    created_at: datetime
    size: int
    version: int


def snapshot_dir(db_path: Path) -> Path:
    return db_path.parent / 'snapshots'


def create_snapshot(db_path: Path, keep: int = DEFAULT_SNAPSHOT_KEEP) -> Path:
    '''复制一份数据库（含 WAL 里尚未落盘的数据），并按 keep 清理旧快照。'''
    directory = snapshot_dir(db_path)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = directory / f'rekindle-{stamp}.db'
    _copy_database(db_path, target)
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
    '''恢复快照，返回恢复前自动保存的「后悔药」快照。

    旧版本的快照先在**临时副本**上升级再恢复（这样 schema 升级过后旧快照仍然可用，
    原快照文件不动）；比程序更新的快照直接拒绝。
    '''
    version = snapshot_version(snapshot_path)
    if version > SCHEMA_VERSION:
        raise SnapshotVersionMismatch(
            version, SCHEMA_VERSION, '快照比程序新，请升级 rekindle'
        )
    if version < SCHEMA_VERSION and not can_upgrade_from(version):
        raise SnapshotVersionMismatch(
            version, SCHEMA_VERSION, '快照太旧，没有迁移路径'
        )

    # keep=0 本次不清理：避免把正在恢复的旧快照顺手删掉。
    safety = create_snapshot(db_path, keep=0)
    with tempfile.TemporaryDirectory() as workdir:
        source = snapshot_path
        if version < SCHEMA_VERSION:
            upgraded = Path(workdir) / 'upgrade.db'
            _copy_database(snapshot_path, upgraded)
            # 用正常仓储打开副本 = 跑与真实库完全相同的迁移步骤。
            SqliteRepo(upgraded).close()
            source = upgraded
        _copy_database(source, db_path)
    return safety


def _prune(directory: Path, keep: int) -> None:
    if keep <= 0:
        return
    files = sorted(directory.glob('rekindle-*.db'))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)
