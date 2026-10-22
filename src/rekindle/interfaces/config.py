'''外壳层共用的位置配置：数据库文件只有一个默认来源。

CLI 与 GUI 都从这里取，避免两处各写一份默认路径。
'''

from __future__ import annotations

import os
from pathlib import Path


def default_db_path() -> Path:
    env = os.environ.get('REKINDLE_DB')
    return Path(env) if env else Path.home() / '.rekindle' / 'rekindle.db'
