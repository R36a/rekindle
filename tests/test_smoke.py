"""骨架期冒烟测试：只验证包可导入、CLI 入口可用。

真正的领域测试从里程碑 M1 开始（见 docs/设计细节.md 第 7 节）。
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from rekindle import __version__
from rekindle.__main__ import build_parser, main


def test_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_parser_prog_name() -> None:
    assert build_parser().prog == "rekindle"


def test_main_without_args_prints_help_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "rekindle" in capsys.readouterr().out


def test_module_entrypoint_reports_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "rekindle", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
