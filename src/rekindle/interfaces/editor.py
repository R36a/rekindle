'''人物编辑窗口：基本信息、公司历史、联系方式、交往记录、归档。'''

from __future__ import annotations

import sqlite3
import tkinter as tk
from collections.abc import Callable
from datetime import date
from functools import partial
from tkinter import messagebox, ttk

from rekindle.app import edit as edit_uc
from rekindle.domain.dates import parse_date_input
from rekindle.domain.errors import RekindleError
from rekindle.domain.fields import DEFAULT_FIELDS
from rekindle.domain.models import Interaction
from rekindle.infra.snapshot import create_snapshot
from rekindle.infra.sqlite_repo import SqliteRepo
from rekindle.interfaces.inputs import split_values


class PersonEditor(tk.Toplevel):
    def __init__(
        self,
        master: tk.Tk,
        repo: SqliteRepo,
        person_id: int,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title('编辑人物')
        self.geometry('900x720')
        self.transient(master)
        self.grab_set()

        person = repo.get_person(person_id)
        if person is None:
            raise ValueError('找不到这个人')

        self._repo = repo
        self._person_id = person_id
        self._on_saved = on_saved
        self._snapshot_done = False
        self._companies = dict(person.companies)
        self._fields = {key: list(values) for key, values in person.fields.items()}
        for spec in DEFAULT_FIELDS:
            self._fields.setdefault(spec.key, [])
        self._interactions: list[Interaction] = repo.list_interactions(person_id)

        self._name_var = tk.StringVar(value=person.display_name)
        self._role = tk.StringVar(value=person.role or '')
        self._company_date = tk.StringVar(value=date.today().isoformat())
        self._company_name = tk.StringVar()
        self._new_values: dict[str, tk.StringVar] = {
            spec.key: tk.StringVar() for spec in DEFAULT_FIELDS
        }
        self._edit_date = tk.StringVar()
        self._edit_summary = tk.StringVar()

        self._build(person.notes or '')
        self._refresh_companies()
        self._refresh_fields()
        self._refresh_interactions()

    def _build(self, notes: str) -> None:
        top = ttk.Frame(self)
        top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='姓名').pack(side='left')
        ttk.Entry(top, textvariable=self._name_var, width=18).pack(side='left', padx=4)
        ttk.Label(top, text='职位').pack(side='left', padx=(12, 0))
        ttk.Entry(top, textvariable=self._role, width=18).pack(side='left', padx=4)

        notes_frame = ttk.LabelFrame(self, text='备注')
        notes_frame.pack(fill='x', padx=8, pady=4)
        self._notes = tk.Text(notes_frame, height=3, wrap='word')
        self._notes.pack(fill='x', padx=6, pady=6)
        self._notes.insert('1.0', notes)

        book = ttk.Notebook(self)
        book.pack(fill='both', expand=True, padx=8, pady=4)
        self._build_companies(book)
        self._build_fields(book)
        self._build_interactions(book)

        bottom = ttk.Frame(self)
        bottom.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(bottom, text='保存', command=self._save).pack(side='left')
        ttk.Button(bottom, text='归档此人', command=self._archive).pack(
            side='left', padx=6
        )
        ttk.Button(bottom, text='取消', command=self.destroy).pack(side='right')

    def _build_companies(self, book: ttk.Notebook) -> None:
        tab = ttk.Frame(book, padding=6)
        book.add(tab, text='公司历史')
        self._company_tree = ttk.Treeview(
            tab, columns=('日期', '公司'), show='headings', height=6
        )
        self._company_tree.heading('日期', text='日期')
        self._company_tree.heading('公司', text='公司')
        self._company_tree.column('日期', width=130, anchor='w')
        self._company_tree.column('公司', width=420, anchor='w')
        self._company_tree.pack(fill='both', expand=True)
        self._company_tree.bind('<<TreeviewSelect>>', self._pick_company)

        form = ttk.Frame(tab)
        form.pack(fill='x', pady=(6, 0))
        ttk.Label(form, text='日期').pack(side='left')
        ttk.Entry(form, textvariable=self._company_date, width=14).pack(
            side='left', padx=4
        )
        ttk.Label(form, text='公司').pack(side='left')
        ttk.Entry(form, textvariable=self._company_name, width=28).pack(
            side='left', padx=4
        )
        ttk.Button(form, text='添加/更新', command=self._add_company).pack(side='left')
        ttk.Button(form, text='删除选中', command=self._remove_company).pack(
            side='left', padx=6
        )

    def _build_fields(self, book: ttk.Notebook) -> None:
        tab = ttk.Frame(book, padding=6)
        book.add(tab, text='联系方式')
        self._field_lists: dict[str, tk.Listbox] = {}
        for row, spec in enumerate(DEFAULT_FIELDS):
            ttk.Label(tab, text=spec.label, width=6).grid(
                row=row, column=0, sticky='ne', pady=4
            )
            listbox = tk.Listbox(tab, height=3, exportselection=False)
            listbox.grid(row=row, column=1, sticky='nsew', padx=4, pady=4)
            self._field_lists[spec.key] = listbox

            right = ttk.Frame(tab)
            right.grid(row=row, column=2, sticky='nw', pady=4)
            ttk.Button(
                right, text='删除选中', command=partial(self._remove_field, spec.key)
            ).pack(anchor='w')
            ttk.Entry(right, textvariable=self._new_values[spec.key], width=22).pack(
                anchor='w', pady=(4, 0)
            )
            ttk.Button(
                right, text='添加', command=partial(self._add_field, spec.key)
            ).pack(anchor='w')
        tab.columnconfigure(1, weight=1)

    def _build_interactions(self, book: ttk.Notebook) -> None:
        tab = ttk.Frame(book, padding=6)
        book.add(tab, text='交往记录')
        self._interaction_tree = ttk.Treeview(
            tab, columns=('id', '日期', '内容'), show='headings', height=7
        )
        for column, width in (('id', 50), ('日期', 120), ('内容', 560)):
            self._interaction_tree.heading(column, text=column)
            self._interaction_tree.column(column, width=width, anchor='w')
        self._interaction_tree.pack(fill='both', expand=True)
        self._interaction_tree.bind('<<TreeviewSelect>>', self._pick_interaction)

        form = ttk.Frame(tab)
        form.pack(fill='x', pady=(6, 0))
        ttk.Label(form, text='日期').pack(side='left')
        ttk.Entry(form, textvariable=self._edit_date, width=14).pack(
            side='left', padx=4
        )
        ttk.Label(form, text='内容').pack(side='left')
        ttk.Entry(form, textvariable=self._edit_summary, width=44).pack(
            side='left', padx=4
        )
        ttk.Button(form, text='保存修改', command=self._save_interaction).pack(
            side='left'
        )
        ttk.Button(form, text='删除', command=self._delete_interaction).pack(
            side='left', padx=6
        )
    # ---------- 刷新 ----------

    def _refresh_companies(self) -> None:
        self._company_tree.delete(*self._company_tree.get_children())
        for day in sorted(self._companies, reverse=True):
            self._company_tree.insert(
                '',
                'end',
                iid=day.isoformat(),
                values=(day.isoformat(), self._companies[day]),
            )

    def _refresh_fields(self) -> None:
        for spec in DEFAULT_FIELDS:
            listbox = self._field_lists[spec.key]
            listbox.delete(0, 'end')
            for value in self._fields.get(spec.key, []):
                listbox.insert('end', value)

    def _refresh_interactions(self) -> None:
        self._interactions = self._repo.list_interactions(self._person_id)
        self._interaction_tree.delete(*self._interaction_tree.get_children())
        for item in self._interactions:
            if item.id is None:
                continue
            self._interaction_tree.insert(
                '',
                'end',
                iid=str(item.id),
                values=(item.id, item.occurred_at.date().isoformat(), item.summary),
            )

    # ---------- 公司历史 ----------

    def _add_company(self) -> None:
        day = parse_date_input(self._company_date.get(), date.today())
        if day is None:
            messagebox.showerror(
                '日期格式不对', '用 YYYY-MM-DD 或 今天/昨天', parent=self
            )
            return
        company = self._company_name.get().strip()
        if not company:
            messagebox.showerror('公司不能为空', '请填写公司名', parent=self)
            return
        self._companies[day] = company
        self._company_name.set('')
        self._refresh_companies()

    def _remove_company(self) -> None:
        selection = self._company_tree.selection()
        if not selection:
            return
        day = date.fromisoformat(selection[0])
        self._companies.pop(day, None)
        self._refresh_companies()

    def _pick_company(self, event: tk.Event) -> None:
        selection = self._company_tree.selection()
        if not selection:
            return
        day = date.fromisoformat(selection[0])
        self._company_date.set(day.isoformat())
        self._company_name.set(self._companies.get(day, ''))

    # ---------- 联系方式 ----------

    def _add_field(self, key: str) -> None:
        values = self._fields.setdefault(key, [])
        for value in split_values(self._new_values[key].get()):
            if value not in values:
                values.append(value)
        self._new_values[key].set('')
        self._refresh_fields()

    def _remove_field(self, key: str) -> None:
        listbox = self._field_lists[key]
        selection = listbox.curselection()  # type: ignore[no-untyped-call]  # tkinter 的 curselection 未标注
        if not selection:
            return
        del self._fields[key][selection[0]]
        self._refresh_fields()

    # ---------- 交往记录 ----------

    def _selected_interaction(self) -> Interaction | None:
        selection = self._interaction_tree.selection()
        if not selection:
            return None
        target = int(selection[0])
        return next(
            (item for item in self._interactions if item.id == target), None
        )

    def _pick_interaction(self, event: tk.Event) -> None:
        item = self._selected_interaction()
        if item is None:
            return
        self._edit_date.set(item.occurred_at.date().isoformat())
        self._edit_summary.set(item.summary)

    def _save_interaction(self) -> None:
        item = self._selected_interaction()
        if item is None:
            messagebox.showinfo('先选一条', '请先在列表里选中一条记录', parent=self)
            return
        day = parse_date_input(self._edit_date.get(), date.today())
        if day is None:
            messagebox.showerror(
                '日期格式不对', '用 YYYY-MM-DD 或 今天/昨天', parent=self
            )
            return
        if not self._snapshot_once():
            return
        try:
            edit_uc.save_interaction(
                self._repo, item, occurred_on=day, summary=self._edit_summary.get()
            )
        except (RekindleError, ValueError) as exc:
            messagebox.showerror('保存失败', str(exc), parent=self)
            return
        self._refresh_interactions()
        self._on_saved()

    def _delete_interaction(self) -> None:
        item = self._selected_interaction()
        if item is None:
            return
        if not messagebox.askyesno(
            '删除记录', '这条交往记录会被删除，继续？', parent=self
        ):
            return
        if not self._snapshot_once():
            return
        try:
            edit_uc.delete_interaction(self._repo, item)
        except (RekindleError, ValueError) as exc:
            messagebox.showerror('删除失败', str(exc), parent=self)
            return
        self._refresh_interactions()
        self._on_saved()

    # ---------- 保存 / 归档 ----------

    def _save(self) -> None:
        if not self._snapshot_once():
            return
        payload = edit_uc.PersonEdit(
            display_name=self._name_var.get(),
            role=self._role.get(),
            notes=self._notes.get('1.0', 'end').strip() or None,
            companies=dict(self._companies),
            fields={key: list(values) for key, values in self._fields.items()},
        )
        try:
            edit_uc.save_person(self._repo, self._person_id, payload)
        except (RekindleError, ValueError) as exc:
            messagebox.showerror('保存失败', str(exc), parent=self)
            return
        self._on_saved()
        self.destroy()

    def _archive(self) -> None:
        if not messagebox.askyesno(
            '归档', '归档后列表里不再显示，数据仍保留。继续？', parent=self
        ):
            return
        if not self._snapshot_once():
            return
        edit_uc.archive_person(self._repo, self._person_id)
        self._on_saved()
        self.destroy()

    def _snapshot_once(self) -> bool:
        if self._snapshot_done:
            return True
        try:
            create_snapshot(self._repo.path)
        except (OSError, sqlite3.Error) as exc:
            messagebox.showerror('快照失败', f'未修改数据库：{exc}', parent=self)
            return False
        self._snapshot_done = True
        return True