'''GUI 冒烟：窗口能建、识别能预填、确认能入库、搜索能过滤。'''

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

tk = pytest.importorskip('tkinter')
gui_module = pytest.importorskip('rekindle.interfaces.gui')
RekindleApp = gui_module.RekindleApp


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    try:
        probe = tk.Tk()
    except tk.TclError:
        pytest.skip('无图形环境')
    probe.destroy()

    # 测试里不弹模态框，否则会卡住整个测试会话。
    monkeypatch.setattr(
        gui_module.messagebox, 'showerror', lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        gui_module.messagebox, 'showinfo', lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        gui_module.messagebox, 'askyesno', lambda *args, **kwargs: True
    )

    instance = RekindleApp(tmp_path / 'gui.db')
    yield instance
    instance.destroy()


def test_识别后确认入库(app: Any) -> None:
    app._text.insert('1.0', '上周和张三在字节工作')
    app.on_extract()

    assert app._capture_id == 1
    assert app._name.get() == '张三'
    assert app._company.get() == '字节'
    assert date.fromisoformat(app._when.get())

    app.on_confirm()

    assert app._capture_id is None
    people = app._repo.list_people()
    assert len(people) == 1
    assert people[0].last_contact_at is not None


def test_空输入不会创建草稿(app: Any) -> None:
    app.on_extract()

    assert app._capture_id is None


def test_丢弃草稿(app: Any) -> None:
    app._text.insert('1.0', '和张三吃饭')
    app.on_extract()
    app.on_discard()

    assert app._capture_id is None
    assert app._repo.list_people() == []


def test_日期格式错误不写库(app: Any) -> None:
    app._text.insert('1.0', '和张三吃饭')
    app.on_extract()
    app._when.set('不是日期')
    app.on_confirm()

    assert app._repo.list_people() == []


def test_重复识别不会堆积草稿(app: Any) -> None:
    app._text.insert('1.0', '和张三吃饭')
    app.on_extract()
    first = app._capture_id
    app.on_extract()

    assert app._capture_id != first
    drafts = [
        row for row in app._repo.export_all()['capture'] if row['status'] == 'draft'
    ]
    assert len(drafts) == 1


def test_搜索过滤列表(app: Any) -> None:
    for text in ('和张三在字节工作', '认识李四'):
        app._text.delete('1.0', 'end')
        app._text.insert('1.0', text)
        app.on_extract()
        app.on_confirm()

    assert len(app._people_tree.get_children()) == 2

    app._query.set('李四')
    app._refresh_people()

    rows = app._people_tree.get_children()
    assert len(rows) == 1
    assert app._people_tree.item(rows[0], 'values')[1] == '李四'


def test_快捷日期按钮(app: Any) -> None:
    app._set_relative_date(-1)
    expected = (datetime.now().date() - timedelta(days=1)).isoformat()
    assert app._when.get() == expected


def test_列表显示最近公司(app: Any) -> None:
    for text in ('上周和张三在字节工作', '今天和张三在腾讯工作'):
        app._text.delete('1.0', 'end')
        app._text.insert('1.0', text)
        app.on_extract()
        app.on_confirm()

    rows = app._people_tree.get_children()
    assert len(rows) == 1
    assert app._people_tree.item(rows[0], 'values')[2] == '腾讯'


def test_联系方式随确认保存(app: Any) -> None:
    app._text.insert('1.0', '和张三吃饭')
    app.on_extract()
    app._field_vars['wechat'].set('wx123')
    app._field_vars['phone'].set('13800000000')

    app.on_confirm()

    people = app._repo.list_people()
    assert people[0].fields == {'wechat': ['wx123'], 'phone': ['13800000000']}


def test_不写句子也能确认(app: Any) -> None:
    app._text.delete('1.0', 'end')
    app._name.set('张三')
    app._company.set('字节')
    app._field_vars['wechat'].set('wx1')

    app.on_confirm()

    people = app._repo.list_people()
    assert people[0].display_name == '张三'
    assert people[0].fields == {'wechat': ['wx1']}
    interactions = app._repo.list_interactions(people[0].id or 0)
    assert interactions[0].summary.startswith('用户输入了：姓名：张三')


def test_一个输入框可以填多个值(app: Any) -> None:
    app._text.insert('1.0', '和张三吃饭')
    app.on_extract()
    app._field_vars['wechat'].set('wx1，wx2')

    app.on_confirm()

    people = app._repo.list_people()
    assert people[0].fields == {'wechat': ['wx1', 'wx2']}


def test_编辑窗口能改资料(app: Any) -> None:
    app._text.insert('1.0', '和张三吃饭')
    app.on_extract()
    app.on_confirm()
    person_id = app._repo.list_people()[0].id or 0

    editor_module = pytest.importorskip('rekindle.interfaces.editor')
    editor = editor_module.PersonEditor(app, app._repo, person_id, lambda: None)
    editor._name_var.set('张三丰')
    editor._save()

    people = app._repo.list_people()
    assert people[0].display_name == '张三丰'
    snapshots = app._repo.path.parent / 'snapshots'
    assert list(snapshots.glob('rekindle-*.db'))
