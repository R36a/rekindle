'''命令行入口：只做转发，真正实现见 interfaces/cli.py（保持本文件"薄"）。'''

from __future__ import annotations

import sys

from rekindle.interfaces.cli import build_parser, main

__all__ = ['build_parser', 'main']


if __name__ == '__main__':
    sys.exit(main())
