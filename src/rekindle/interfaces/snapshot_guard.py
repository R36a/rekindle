'''写前快照：同一个对话框内只备份一次，失败就不改数据。'''

from __future__ import annotations

import sqlite3
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox

from rekindle.infra.snapshot import create_snapshot


@dataclass
class SnapshotGuard:
    '''一个对话框内的多次写操作只做一次快照，避免把 keep 份数挤掉。'''

    db_path: Path
    _done: bool = field(default=False, init=False)

    def before_write(self, parent: tk.Misc | None = None) -> bool:
        '''成功返回 True；失败弹提示并返回 False（不会写入数据）。'''
        if self._done:
            return True
        try:
            create_snapshot(self.db_path)
        except (OSError, sqlite3.Error) as exc:
            if parent is None:
                messagebox.showerror('快照失败', f'未修改数据库：{exc}')
            else:
                messagebox.showerror('快照失败', f'未修改数据库：{exc}', parent=parent)
            return False
        self._done = True
        return True
