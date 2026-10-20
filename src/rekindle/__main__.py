"""命令行入口。

里程碑 1 只提供 --version / --help；业务子命令随开发文档的里程碑逐步加入。
保持本文件"薄"：只负责参数解析与依赖装配，不放业务逻辑。
"""

from __future__ import annotations

import argparse
import sys

from rekindle import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rekindle",
        description="本地优先的个人人脉管理器（开发中）",
    )
    parser.add_argument("--version", action="version", version=f"rekindle {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
