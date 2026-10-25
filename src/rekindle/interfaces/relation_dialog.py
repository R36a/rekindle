'''添加关系：选已有联系人，或先新建联系人再建立关系。

规则：新建联系人时只额外记录「张三介绍李四」，不会自动补一条「朋友」边；
关系类型是用户明确选择的认识关系。
'''

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import date, datetime
from tkinter import messagebox, ttk

from rekindle.app import record
from rekindle.app import relations as relation_uc
from rekindle.domain.errors import RekindleError
from rekindle.domain.fields import DEFAULT_FIELDS
from rekindle.domain.person_schema import CONTACT_KEYS
from rekindle.domain.relations import (
    KIND_BY_LABEL,
    SELECTABLE_LABELS,
    RelationKind,
)
from rekindle.domain.text import clean_optional
from rekindle.infra.sqlite_repo import SqliteRepo
from rekindle.interfaces.forms import build_grid, table_columns
from rekindle.interfaces.inputs import split_values
from rekindle.interfaces.snapshot_guard import SnapshotGuard
from rekindle.interfaces.ui import make_table


class RelationDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Tk | tk.Toplevel,
        repo: SqliteRepo,
        person_id: int,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(master)
        person = repo.get_person(person_id)
        if person is None:
            raise ValueError('找不到这个人')

        self.title(f'给 {person.display_name} 添加关系')
        self.geometry('760x660')
        self.transient(master)
        self.grab_set()

        self._repo = repo
        self._person_id = person_id
        self._on_saved = on_saved
        self._snapshots = SnapshotGuard(repo.path)
        self._selected_id: int | None = None

        self._search = tk.StringVar()
        self._name_var = tk.StringVar()
        self._company = tk.StringVar()
        self._role = tk.StringVar()
        self._field_vars = {
            spec.key: tk.StringVar() for spec in DEFAULT_FIELDS
        }
        self._form_vars = {
            'display_name': self._name_var,
            'company': self._company,
            'role': self._role,
        }
        self._kind = tk.StringVar(value='朋友')
        self._note = tk.StringVar()
        self._status = tk.StringVar(
            value='选中已有联系人；或直接在下面填姓名新建'
        )

        self._build()
        self._refresh_candidates()

    def _build(self) -> None:
        choose = ttk.LabelFrame(self, text='① 选择已有联系人')
        choose.pack(fill='both', expand=True, padx=8, pady=(8, 4))

        search_row = ttk.Frame(choose)
        search_row.pack(fill='x', padx=6, pady=4)
        ttk.Label(search_row, text='搜索').pack(side='left')
        entry = ttk.Entry(search_row, textvariable=self._search, width=32)
        entry.pack(side='left', padx=4)
        entry.bind('<KeyRelease>', self._on_search)
        ttk.Button(search_row, text='清空', command=self._clear_search).pack(
            side='left'
        )

        self._candidates = make_table(
            choose,
            table_columns(
                ('display_name', 160), ('company', 240), ('role', 160)
            ),
            height=7,
            padx=6,
            pady=(0, 6),
        )
        self._candidates.bind('<<TreeviewSelect>>', self._pick_candidate)

        create = ttk.LabelFrame(self, text='② 不在库里：先新建联系人')
        create.pack(fill='x', padx=8, pady=4)
        top = ttk.Frame(create)
        top.pack(fill='x', padx=6, pady=(6, 0))
        # 标签与宽度来自注册表：姓名/公司/职位三项。
        self._form_widgets = build_grid(
            top, ('display_name', 'company', 'role'), self._form_vars
        )

        contact = ttk.Frame(create)
        contact.pack(fill='x', padx=6, pady=(4, 2))
        build_grid(contact, CONTACT_KEYS, self._field_vars)
        ttk.Label(
            create, text='（选中上方联系人后，这里的内容会被忽略）'
        ).pack(anchor='w', padx=6, pady=(0, 4))

        relation = ttk.LabelFrame(self, text='③ 关系')
        relation.pack(fill='x', padx=8, pady=4)
        row = ttk.Frame(relation)
        row.pack(fill='x', padx=6, pady=6)
        ttk.Label(row, text='关系类型').pack(side='left')
        ttk.Combobox(
            row,
            textvariable=self._kind,
            values=list(SELECTABLE_LABELS),
            state='readonly',
            width=10,
        ).pack(side='left', padx=6)
        ttk.Label(row, text='备注').pack(side='left', padx=(12, 0))
        ttk.Entry(row, textvariable=self._note, width=38).pack(
            side='left', padx=6
        )

        bottom = ttk.Frame(self)
        bottom.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Label(bottom, textvariable=self._status).pack(side='left')
        ttk.Button(bottom, text='取消', command=self.destroy).pack(side='right')
        ttk.Button(bottom, text='保存', command=self._save).pack(
            side='right', padx=6
        )

    # ---------- 选择 ----------

    def _on_search(self, event: tk.Event) -> None:
        self._selected_id = None
        self._refresh_candidates()

    def _clear_search(self) -> None:
        self._search.set('')
        self._selected_id = None
        self._refresh_candidates()

    def _refresh_candidates(self) -> None:
        query = self._search.get().strip()
        people = [
            person
            for person in self._repo.list_people(query, 100)
            if person.id != self._person_id
        ]
        self._candidates.delete(*self._candidates.get_children())
        for person in people:
            self._candidates.insert(
                '',
                'end',
                iid=str(person.id or 0),
                values=(
                    person.display_name,
                    person.current_company or '',
                    person.role or '',
                ),
            )
        if self._selected_id is None:
            self._status.set(f'找到 {len(people)} 人；选中一个，或在下面新建')

    def _pick_candidate(self, event: tk.Event) -> None:
        selection = self._candidates.selection()
        if not selection:
            return
        self._selected_id = int(selection[0])
        person = self._repo.get_person(self._selected_id)
        if person is not None:
            self._status.set(f'已选择：{person.display_name}（#{person.id}）')

    # ---------- 保存 ----------

    def _save(self) -> None:
        kind = KIND_BY_LABEL.get(self._kind.get())
        if kind is None:
            messagebox.showerror('关系类型不对', '请选择关系类型', parent=self)
            return

        note = clean_optional(self._note.get())
        if self._selected_id is None and not self._name_var.get().strip():
            messagebox.showerror(
                '缺少姓名',
                '请选择已有联系人，或填写新联系人姓名',
                parent=self,
            )
            return
        if not self._snapshots.before_write(self):
            return

        now = datetime.now()
        try:
            if self._selected_id is not None:
                relation_uc.add_relation(
                    self._repo,
                    person_id=self._person_id,
                    other_id=self._selected_id,
                    kind=kind,
                    note=note,
                    now=now,
                )
            else:
                self._create_and_link(kind, note, now)
        except (RekindleError, ValueError) as exc:
            messagebox.showerror('保存失败', str(exc), parent=self)
            return

        self._on_saved()
        self.destroy()

    def _create_and_link(
        self, kind: RelationKind, note: str | None, now: datetime
    ) -> None:
        '''新建联系人 + 记介绍 + 记关系：三步要么全成，要么全不成。

        以前每一步各自提交，第二步失败会留下「人建了、关系没建」；
        现在包在可嵌套的 atomic() 里（record.manual 内部也用 atomic，复用外层）。
        '''
        name = self._name_var.get().strip()
        if not name:
            raise ValueError('请选择已有联系人，或填写新联系人姓名')
        fields = {
            key: split_values(var.get())
            for key, var in self._field_vars.items()
            if var.get().strip()
        }
        with self._repo.atomic():
            result = record.manual(
                self._repo,
                now=now,
                display_name=name,
                company=self._company.get(),
                role=self._role.get(),
                fields=fields,
                occurred_on=date.today(),
            )
            relation_uc.add_introduction(
                self._repo,
                introducer_id=self._person_id,
                introduced_id=result.person_id,
                note=None,
                now=now,
            )
            relation_uc.add_relation(
                self._repo,
                person_id=self._person_id,
                other_id=result.person_id,
                kind=kind,
                note=note,
                now=now,
            )

