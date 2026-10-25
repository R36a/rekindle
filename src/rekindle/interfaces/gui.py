'''Tkinter 图形界面：记一句话 → 确认入库 → 搜索查看。零额外依赖。

产品只做两件事：**快速记人、快速查人**（提醒/待办已移除）。
启动：python -m rekindle.gui   或安装后的 rekindle-gui
'''

from __future__ import annotations

import argparse
import contextlib
import sys
import tkinter as tk
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from tkinter import messagebox, ttk

from rekindle.app import queries, record
from rekindle.app import relations as relation_uc
from rekindle.domain.errors import RekindleError, RelationExists
from rekindle.domain.fields import DEFAULT_FIELDS
from rekindle.domain.limits import MAX_LIST_LIMIT
from rekindle.domain.text import clean_optional
from rekindle.infra.sqlite_repo import SqliteRepo
from rekindle.interfaces.config import default_db_path
from rekindle.interfaces.editor import PersonEditor
from rekindle.interfaces.inputs import split_values
from rekindle.interfaces.snapshot_dialog import SnapshotDialog
from rekindle.interfaces.ui import fill_person_choices, make_table, read_date

_PEOPLE_COLUMNS = {'ID': 40, '姓名': 140, '公司': 140, '职位': 100, '最近联系': 110}


class RekindleApp(tk.Tk):
    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.title('rekindle — 本地人脉（离线）')
        self.geometry('820x700')
        self.minsize(700, 560)
        self._set_window_icon()
        self._repo = SqliteRepo(db_path)
        self._capture_id: int | None = None

        self._name = tk.StringVar()
        self._company = tk.StringVar()
        self._role = tk.StringVar()
        self._when = tk.StringVar(value=datetime.now().date().isoformat())
        self._field_vars: dict[str, tk.StringVar] = {
            spec.key: tk.StringVar() for spec in DEFAULT_FIELDS
        }
        self._query = tk.StringVar()
        self._status = tk.StringVar(value=f'数据库：{db_path}')
        self._introduced_by = tk.StringVar()
        self._introducer_ids: dict[str, int] = {}

        self._build()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.refresh()

    # ---------- 布局 ----------

    def _set_window_icon(self) -> None:
        '''打包后用自带图标；源码运行时找不到就跳过。'''
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3]))
        icon = base / 'assets' / 'rekindle.ico'
        if icon.exists():
            with contextlib.suppress(tk.TclError):
                # tkinter 的 iconbitmap 没有类型标注（同 editor.py 的 curselection）
                self.iconbitmap(default=str(icon))  # type: ignore[no-untyped-call]

    def _build(self) -> None:
        capture = ttk.LabelFrame(self, text='① 输入一句话（Ctrl+Enter 识别）')
        capture.pack(fill='x', padx=8, pady=(8, 4))
        self._text = tk.Text(capture, height=3, wrap='word')
        self._text.pack(fill='x', padx=6, pady=6)
        self._text.bind('<Control-Return>', self._on_shortcut)
        self._text.focus_set()

        row = ttk.Frame(capture)
        row.pack(fill='x', padx=6, pady=(0, 6))
        ttk.Button(row, text='识别', command=self.on_extract).pack(side='left')
        ttk.Label(row, text='离线规则抽取，不联网；识别只预填，点「确认入库」才写入').pack(
            side='left', padx=8
        )

        preview = ttk.LabelFrame(self, text='② 核对并确认（字段可改）')
        preview.pack(fill='x', padx=8, pady=4)
        fields = (
            ('姓名', self._name),
            ('公司', self._company),
            ('职位', self._role),
            ('日期 ', self._when),
        )
        for index, (label, var) in enumerate(fields):
            grid_row, grid_col = divmod(index, 2)
            ttk.Label(preview, text=label).grid(
                row=grid_row, column=grid_col * 2, sticky='e', padx=4, pady=3
            )
            ttk.Entry(preview, textvariable=var, width=26).grid(
                row=grid_row, column=grid_col * 2 + 1, sticky='we', padx=4, pady=3
            )
        preview.columnconfigure(1, weight=1)
        preview.columnconfigure(3, weight=1)

        contact = ttk.Frame(preview)
        contact.grid(row=2, column=0, columnspan=4, sticky='we', padx=4, pady=(2, 0))
        for index, spec in enumerate(DEFAULT_FIELDS):
            grid_row, grid_col = divmod(index, 2)
            ttk.Label(contact, text=spec.label).grid(
                row=grid_row, column=grid_col * 2, sticky='e', padx=4, pady=3
            )
            ttk.Entry(
                contact, textvariable=self._field_vars[spec.key], width=26
            ).grid(
                row=grid_row, column=grid_col * 2 + 1, sticky='we', padx=4, pady=3
            )
        contact.columnconfigure(1, weight=1)
        contact.columnconfigure(3, weight=1)

        intro = ttk.Frame(preview)
        intro.grid(row=3, column=0, columnspan=4, sticky='we', padx=4, pady=3)
        ttk.Label(intro, text='通过谁认识').pack(side='left')
        self._introducer_combo = ttk.Combobox(
            intro,
            textvariable=self._introduced_by,
            state='readonly',
            width=34,
        )
        self._introducer_combo.pack(side='left', padx=4)
        ttk.Label(intro, text='（可选；只记录介绍关系）').pack(side='left')

        quick = ttk.Frame(preview)
        quick.grid(row=4, column=0, columnspan=4, sticky='w', padx=4, pady=(0, 2))
        ttk.Label(quick, text='日期快捷：').pack(side='left')
        for label, days in (('今天', 0), ('昨天', -1), ('前天', -2), ('上周', -7)):
            ttk.Button(
                quick,
                text=label,
                width=6,
                command=partial(self._set_relative_date, days),
            ).pack(side='left', padx=2)

        actions = ttk.Frame(preview)
        actions.grid(row=5, column=0, columnspan=4, sticky='w', padx=4, pady=(4, 6))
        ttk.Button(actions, text='确认入库', command=self.on_confirm).pack(side='left')
        ttk.Button(actions, text='丢弃草稿', command=self.on_discard).pack(
            side='left', padx=6
        )

        browser = ttk.LabelFrame(self, text='③ 查找联系人（Ctrl+F）')
        browser.pack(fill='both', expand=True, padx=8, pady=4)
        search_row = ttk.Frame(browser)
        search_row.pack(fill='x', padx=6, pady=(6, 2))
        ttk.Label(search_row, text='搜索').pack(side='left')
        self._search = ttk.Entry(search_row, textvariable=self._query, width=32)
        self._search.pack(side='left', padx=6)
        self._search.bind('<KeyRelease>', self.on_search)
        self._search.bind('<Escape>', self._on_escape_search)
        ttk.Button(search_row, text='清空', command=self._clear_search).pack(side='left')

        self._people_tree = make_table(
            browser, _PEOPLE_COLUMNS, height=10, padx=6, pady=(2, 6)
        )
        self._people_tree.bind('<Double-1>', self.on_person_detail)

        bottom = ttk.Frame(self)
        bottom.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(bottom, text='编辑选中', command=self.open_editor).pack(
            side='left', padx=6
        )
        ttk.Button(bottom, text='刷新', command=self.refresh).pack(side='left')
        ttk.Button(bottom, text='快照', command=self.open_snapshots).pack(
            side='left', padx=6
        )
        ttk.Label(bottom, textvariable=self._status).pack(side='right')

        self.bind('<Control-f>', self._focus_search)

    # ---------- 事件 ----------

    def _on_shortcut(self, event: tk.Event) -> str:
        self.on_extract()
        return 'break'

    def on_extract(self) -> None:
        text = self._text.get('1.0', 'end').strip()
        if not text:
            self._set_status('可以不写句子：直接填姓名等字段后点「确认入库」')
            return
        # 重复点「识别」时先丢掉上一份草稿，避免库里堆积用不上的 draft。
        if self._capture_id is not None:
            with contextlib.suppress(RekindleError):
                self._repo.discard_capture(self._capture_id)
        try:
            saved = record.record(self._repo, text, datetime.now())
        except (RekindleError, ValueError) as exc:
            messagebox.showerror('识别失败', str(exc), parent=self)
            return

        self._capture_id = saved.capture_id
        parsed = saved.parsed
        self._name.set(parsed.display_name or '')
        self._company.set(parsed.company or '')
        self._role.set(parsed.role or '')
        self._when.set(parsed.occurred_at.isoformat() if parsed.occurred_at else '')
        for var in self._field_vars.values():
            var.set('')
        self._set_status(f'草稿 capture #{saved.capture_id}：核对后点「确认入库」')

    def on_confirm(self) -> None:
        text = self._text.get('1.0', 'end').strip()
        # 有原话但还没识别：自动识别一次，省一次点击。
        if self._capture_id is None and text:
            self.on_extract()

        if self._capture_id is None and not self._name.get().strip():
            self._set_status('姓名是必填字段：写一句原话，或直接填姓名')
            return

        when_text = self._when.get().strip()
        occurred_on = read_date(self, when_text) if when_text else None
        if when_text and occurred_on is None:
            return

        fields = {
            key: split_values(var.get())
            for key, var in self._field_vars.items()
            if var.get().strip()
        }
        capture_id = self._capture_id
        was_manual = capture_id is None
        try:
            if capture_id is None:
                result = record.manual(
                    self._repo,
                    now=datetime.now(),
                    name=self._name.get(),
                    company=self._company.get(),
                    role=self._role.get(),
                    fields=fields,
                    occurred_on=occurred_on,
                )
            else:
                result = record.confirm(
                    self._repo,
                    capture_id,
                    now=datetime.now(),
                    name=clean_optional(self._name.get()),
                    company=clean_optional(self._company.get()),
                    role=clean_optional(self._role.get()),
                    fields=fields,
                    occurred_on=occurred_on,
                )
        except (RekindleError, ValueError) as exc:
            messagebox.showerror('确认失败', str(exc), parent=self)
            return

        introducer_id = self._introducer_ids.get(self._introduced_by.get())
        if introducer_id is not None and introducer_id != result.person_id:
            try:
                relation_uc.add_introduction(
                    self._repo,
                    introducer_id=introducer_id,
                    introduced_id=result.person_id,
                    note=None,
                    now=datetime.now(),
                )
            except RelationExists:
                pass
            except (RekindleError, ValueError) as exc:
                messagebox.showwarning(
                    '介绍关系未保存', str(exc), parent=self
                )

        self._clear_preview()
        self.refresh()
        mode = '手动填写' if was_manual else '来自草稿'
        self._set_status(
            f'已入库：{result.person_name}（#{result.person_id}，{mode}）'
        )

    def on_discard(self) -> None:
        if self._capture_id is None:
            self._set_status('当前没有草稿')
            return
        try:
            self._repo.discard_capture(self._capture_id)
        except RekindleError as exc:
            messagebox.showerror('丢弃失败', str(exc), parent=self)
            return
        self._clear_preview()
        self._set_status('草稿已丢弃')

    # ---------- 查找 ----------

    def on_search(self, event: tk.Event) -> None:
        self._refresh_people()

    def _on_escape_search(self, event: tk.Event) -> str:
        self._query.set('')
        self._refresh_people()
        self._text.focus_set()
        return 'break'

    def _clear_search(self) -> None:
        self._query.set('')
        self._refresh_people()

    def _focus_search(self, event: tk.Event) -> str:
        self._search.focus_set()
        self._search.select_range(0, 'end')
        return 'break'

    def refresh(self) -> None:
        self._refresh_people()
        self._refresh_introducers()

    def _refresh_introducers(self) -> None:
        self._introducer_ids = fill_person_choices(
            self._introducer_combo,
            self._introduced_by,
            self._repo.list_people('', MAX_LIST_LIMIT),
        )

    def _refresh_people(self) -> None:
        query = self._query.get().strip()
        people = queries.list_people(self._repo, query, MAX_LIST_LIMIT)
        self._people_tree.delete(*self._people_tree.get_children())
        for person in people:
            last = ''
            if person.last_contact_at is not None:
                last = person.last_contact_at.date().isoformat()
            self._people_tree.insert(
                '',
                'end',
                iid=str(person.id or 0),
                values=(
                    person.id,
                    person.display_name,
                    person.current_company or '',
                    person.role or '',
                    last,
                ),
            )
        suffix = f'（搜索：{query}）' if query else ''
        self._set_status(f'{len(people)} 人{suffix}')

    def on_person_detail(self, event: tk.Event) -> None:
        self.open_editor()

    def open_editor(self) -> None:
        selection = self._people_tree.selection()
        if not selection:
            self._set_status('先选中一个人')
            return
        try:
            PersonEditor(self, self._repo, int(selection[0]), self._after_edit)
        except (RekindleError, ValueError) as exc:
            messagebox.showerror('打开失败', str(exc), parent=self)

    def _after_edit(self) -> None:
        self.refresh()
        self._set_status('已保存')

    def open_snapshots(self) -> None:
        SnapshotDialog(self, self._repo.path, self._after_restore)

    def _after_restore(self) -> None:
        path = self._repo.path
        self._repo.close()
        self._repo = SqliteRepo(path)
        self.refresh()
        self._set_status('已恢复快照')

    # ---------- 内部 ----------

    def _set_relative_date(self, days: int) -> None:
        '''快捷按钮：按相对今天的天数填日期。'''
        self._when.set((datetime.now().date() + timedelta(days=days)).isoformat())

    def _set_status(self, text: str) -> None:
        self._status.set(text)

    def _clear_preview(self) -> None:
        self._capture_id = None
        self._text.delete('1.0', 'end')
        for var in (self._name, self._company, self._role):
            var.set('')
        self._when.set(datetime.now().date().isoformat())
        for var in self._field_vars.values():
            var.set('')
        self._introduced_by.set('')

    def _on_close(self) -> None:
        self._repo.close()
        self.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='rekindle-gui', description='rekindle 图形界面（离线原型）'
    )
    parser.add_argument('--db', default=str(default_db_path()))
    args = parser.parse_args(argv)
    app = RekindleApp(Path(args.db))
    app.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
