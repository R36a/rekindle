'''快照列表与恢复窗口。'''

from __future__ import annotations

import sqlite3
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from rekindle.domain.errors import RekindleError
from rekindle.infra.snapshot import (
    SnapshotInfo,
    create_snapshot,
    list_snapshots,
    restore_snapshot,
)
from rekindle.interfaces.format import human_size
from rekindle.interfaces.ui import make_table


class SnapshotDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Tk,
        db_path: Path,
        on_restored: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title('数据库快照')
        self.geometry('780x420')
        self.transient(master)
        self.grab_set()

        self._db_path = db_path
        self._on_restored = on_restored
        self._infos: list[SnapshotInfo] = []
        self._status = tk.StringVar()

        self._tree = make_table(
            self,
            {'时间': 160, '大小': 90, '版本': 60, '文件': 400},
            height=10,
            padx=8,
            pady=8,
        )

        bottom = ttk.Frame(self)
        bottom.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(bottom, text='立即备份', command=self._backup).pack(side='left')
        ttk.Button(bottom, text='恢复选中', command=self._restore).pack(
            side='left', padx=6
        )
        ttk.Button(bottom, text='关闭', command=self.destroy).pack(side='right')
        ttk.Label(bottom, textvariable=self._status).pack(side='right', padx=8)

        self._refresh()

    def _refresh(self) -> None:
        self._infos = list_snapshots(self._db_path)
        self._tree.delete(*self._tree.get_children())
        for info in self._infos:
            self._tree.insert(
                '',
                'end',
                iid=str(info.path),
                values=(
                    info.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    human_size(info.size),
                    f'v{info.version}',
                    info.path.name,
                ),
            )
        self._status.set(f'{len(self._infos)} 份快照')

    def _selected(self) -> SnapshotInfo | None:
        selection = self._tree.selection()
        if not selection:
            return None
        target = selection[0]
        return next(
            (info for info in self._infos if str(info.path) == target), None
        )

    def _backup(self) -> None:
        try:
            path = create_snapshot(self._db_path)
        except (OSError, sqlite3.Error) as exc:
            messagebox.showerror('备份失败', str(exc), parent=self)
            return
        self._refresh()
        self._status.set(f'已备份：{path.name}')

    def _restore(self) -> None:
        info = self._selected()
        if info is None:
            messagebox.showinfo('先选一份', '请先在列表里选中要恢复的快照', parent=self)
            return
        if not messagebox.askyesno(
            '恢复快照',
            '将用这份快照覆盖当前数据库。\n恢复前会自动再备份当前数据。\n\n继续？',
            parent=self,
        ):
            return
        try:
            safety = restore_snapshot(self._db_path, info.path)
        except (RekindleError, OSError, sqlite3.Error) as exc:
            messagebox.showerror('恢复失败', str(exc), parent=self)
            return
        self._on_restored()
        self._refresh()
        messagebox.showinfo(
            '已恢复',
            f'已恢复到 {info.created_at:%Y-%m-%d %H:%M:%S} 的快照。\n'
            f'恢复前的数据已备份为：{safety.name}',
            parent=self,
        )
