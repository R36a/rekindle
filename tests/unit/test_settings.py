'''设置与权限的测试：验证「默认最小权限」在代码层生效。'''

from __future__ import annotations

import pytest

from rekindle.domain.models import (
    DEFAULT_SNAPSHOT_KEEP,
    Permission,
    PermissionDenied,
    Settings,
)


def test_默认最小权限() -> None:
    s = Settings()
    assert s.ai_add_field is False
    assert s.ai_delete_field is False
    assert s.ai_auto_commit is False
    assert s.ai_snapshot is False


def test_存档默认开启() -> None:
    s = Settings()
    assert s.auto_snapshot is True
    assert s.snapshot_keep == DEFAULT_SNAPSHOT_KEEP


def test_allows_返回对应开关() -> None:
    assert Settings(ai_add_field=True).allows(Permission.ADD_FIELD) is True
    assert Settings().allows(Permission.ADD_FIELD) is False


def test_require_未开启会抛错() -> None:
    with pytest.raises(PermissionDenied):
        Settings().require(Permission.AUTO_COMMIT)


def test_require_开启后不抛错() -> None:
    Settings(ai_auto_commit=True).require(Permission.AUTO_COMMIT)


def test_设置可随时收回() -> None:
    s = Settings(ai_add_field=True)
    s.ai_add_field = False
    assert s.allows(Permission.ADD_FIELD) is False
