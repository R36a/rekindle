"""rekindle —— 本地优先的个人人脉管理器。

设计文档见 docs/开发文档.md。
"""

from __future__ import annotations

# 版本号的唯一来源（single source of truth）。
# pyproject.toml 通过 [tool.setuptools.dynamic] 从这里读取，不要再在别处手写版本号。
__version__ = "0.1.0"
__all__ = ["__version__"]
