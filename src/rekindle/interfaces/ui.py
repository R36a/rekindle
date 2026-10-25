'''界面共用部件与交互：一处实现，各窗口引用。

收进来的都是**已经重复过**的东西，不是「以后可能用到」：
- `make_table`：表头 + 列宽 + 滚动条（原来 6 处各写一遍，其中 2 处忘了滚动条）
- `read_date`：日期输入解析 + 报错（原来 3 处各写一遍，提示文案还漂移过）
- `fill_person_choices`：「姓名 (#id)」下拉（主界面与编辑窗各写一遍）
'''

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable
from datetime import date
from tkinter import messagebox, ttk

from rekindle.domain.dates import RELATIVE_DAYS, parse_date_input
from rekindle.domain.models import Person


def make_table(
    parent: tk.Misc,
    columns: dict[str, int],
    *,
    height: int = 8,
    padx: int | tuple[int, int] = 0,
    pady: int | tuple[int, int] = 0,
) -> ttk.Treeview:
    '''表头 + 列宽 + 垂直滚动条一次配好；调用方只负责 insert / bind。

    columns 用 dict 而不是两个元组：顺序与列宽必须在同一处，避免 zip 对不齐。
    '''
    holder = ttk.Frame(parent)
    holder.pack(fill='both', expand=True, padx=padx, pady=pady)

    tree = ttk.Treeview(
        holder, columns=tuple(columns), show='headings', height=height
    )
    for name, width in columns.items():
        tree.heading(name, text=name)
        tree.column(name, width=width, anchor='w')

    bar = ttk.Scrollbar(holder, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side='left', fill='both', expand=True)
    bar.pack(side='right', fill='y')
    return tree


def read_date(parent: tk.Misc, text: str) -> date | None:
    '''解析界面上的日期；不合法就提示并返回 None（调用方拿到 None 直接 return）。

    提示里列出的相对词来自 RELATIVE_DAYS，不另写一份清单。
    '''
    day = parse_date_input(text, date.today())
    if day is None:
        messagebox.showerror(
            '日期格式不对',
            '日期用 YYYY-MM-DD，或相对词：' + '、'.join(RELATIVE_DAYS),
            parent=parent,
        )
    return day


def fill_person_choices(
    combo: ttk.Combobox,
    var: tk.StringVar,
    people: Iterable[Person],
    *,
    exclude_id: int | None = None,
) -> dict[str, int]:
    '''把「姓名 (#id)」填进下拉框，返回 标签 → id 的映射（含空串）。

    exclude_id 用来把自己从介绍人候选里去掉（编辑自己的资料时）。
    '''
    mapping = {
        f'{person.display_name} (#{person.id})': person.id
        for person in people
        if person.id is not None and person.id != exclude_id
    }
    values: tuple[str, ...] = ('', *mapping)
    combo.configure(values=values)
    if var.get() not in values:
        var.set('')
    return mapping
