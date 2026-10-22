'''集成测试共用：用临时真实 sqlite 文件（顺带验证建表与迁移）。'''

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from rekindle.infra.sqlite_repo import SqliteRepo

NOW = datetime(2026, 10, 22, 9, 0)


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[SqliteRepo]:
    instance = SqliteRepo(tmp_path / 'test.db')
    yield instance
    instance.close()
