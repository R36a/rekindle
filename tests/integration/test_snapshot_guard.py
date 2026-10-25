'''写前快照：同一对话框只备份一次；失败时拒绝写入。'''

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rekindle.infra.snapshot import list_snapshots
from rekindle.infra.sqlite_repo import SqliteRepo
from rekindle.interfaces import snapshot_guard


def test_同一对话框只快照一次(tmp_path: Path) -> None:
    db = tmp_path / 'guard.db'
    SqliteRepo(db).close()

    guard = snapshot_guard.SnapshotGuard(db)
    assert guard.before_write() is True
    assert guard.before_write() is True

    assert len(list_snapshots(db)) == 1


def test_快照失败时拒绝写入(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        snapshot_guard.messagebox, 'showerror', lambda *args, **kwargs: None
    )

    def boom(path: Path, keep: int = 10) -> Path:
        raise sqlite3.Error('boom')

    monkeypatch.setattr(snapshot_guard, 'create_snapshot', boom)

    guard = snapshot_guard.SnapshotGuard(tmp_path / 'guard.db')
    assert guard.before_write() is False
