'''人员表单的构建器：标签文案、输入框宽度、单行/多行都来自字段注册表。

三个窗口（主界面确认 / 编辑资料 / 关系对话框新建）共用这一个实现，
不再各写一遍 `ttk.Label(text='姓名') + ttk.Entry(...)` 的两行样板。

槽位有两种：
- 字段 key（字符串）：标签与宽度来自 `person_schema`，变量从 `variables[key]` 取；
- `(标签, 变量, 宽度)`：窗口专属项（如「日期」属于交往记录，不是 Person 字段）。
'''

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable, Mapping
from tkinter import ttk

from rekindle.domain.person_schema import FIELD_BY_KEY

Slot = str | tuple[str, tk.StringVar, int]


def table_columns(*pairs: tuple[str, int]) -> dict[str, int]:
    '''`(字段 key, 列宽)` → `{表头文案: 列宽}`。

    表头文案来自注册表（改字段名只改一处）；列宽是各界面自己的排版决定，留在调用处。
    '''
    return {FIELD_BY_KEY[key].label: width for key, width in pairs}


def build_grid(
    parent: tk.Misc,
    slots: Iterable[Slot],
    variables: Mapping[str, tk.StringVar],
    *,
    columns: int = 2,
    pady: int = 3,
) -> dict[str, tk.Widget]:
    '''把「标签 + 输入框」按 columns 列排进 parent，返回 key → 控件。'''
    widgets: dict[str, tk.Widget] = {}
    for index, slot in enumerate(slots):
        row, column = divmod(index, columns)
        if isinstance(slot, str):
            field = FIELD_BY_KEY[slot]
            label, width = field.label, field.width
            widget: tk.Widget = ttk.Entry(
                parent, textvariable=variables[slot], width=width
            )
            widgets[slot] = widget
        else:
            label, var, width = slot
            widget = ttk.Entry(parent, textvariable=var, width=width)

        ttk.Label(parent, text=label).grid(
            row=row, column=column * 2, sticky='e', padx=4, pady=pady
        )
        widget.grid(row=row, column=column * 2 + 1, sticky='we', padx=4, pady=pady)

    for index in range(columns):
        parent.columnconfigure(index * 2 + 1, weight=1)
    return widgets
