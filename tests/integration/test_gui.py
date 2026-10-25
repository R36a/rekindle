'''GUI 冒烟：窗口能建、识别能预填、确认能入库、搜索能过滤。'''

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from rekindle.app import relations as relation_uc
from rekindle.domain.errors import InvalidRelation
from rekindle.domain.models import Person
from rekindle.domain.relations import RelationKind

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


def test_确认支持相对日期(app: Any) -> None:
    app._text.insert('1.0', '和张三吃饭')
    app.on_extract()
    app._when.set('昨天')

    app.on_confirm()

    people = app._repo.list_people()
    assert len(people) == 1
    assert people[0].last_contact_at is not None
    expected = (datetime.now() - timedelta(days=1)).date()
    assert people[0].last_contact_at.date() == expected


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


def test_快照窗口能恢复(app: Any) -> None:
    app._text.insert('1.0', '和张三吃饭')
    app.on_extract()
    app.on_confirm()

    from rekindle.infra.snapshot import create_snapshot

    create_snapshot(app._repo.path)

    app._text.insert('1.0', '和李四吃饭')
    app.on_extract()
    app.on_confirm()
    assert len(app._repo.list_people()) == 2

    dialog_module = pytest.importorskip('rekindle.interfaces.snapshot_dialog')
    dialog = dialog_module.SnapshotDialog(
        app, app._repo.path, app._after_restore
    )
    rows = dialog._tree.get_children()
    assert rows
    dialog._tree.selection_set(rows[0])
    dialog._restore()

    assert [p.display_name for p in app._repo.list_people()] == ['张三']
    dialog.destroy()


def test_主界面可以记录介绍人(app: Any) -> None:
    app._text.delete('1.0', 'end')
    app._name.set('张三')
    app.on_confirm()
    zhang = app._repo.list_people()[0].id or 0

    app._name.set('李四')
    app._introduced_by.set(f'张三 (#{zhang})')
    app.on_confirm()

    li = next(
        person
        for person in app._repo.list_people()
        if person.display_name == '李四'
    )
    relations = app._repo.list_relations(li.id or 0)
    assert len(relations) == 1
    assert relations[0].kind == RelationKind.INTRODUCED
    assert relations[0].person_a_id == zhang
    assert relations[0].person_b_id == li.id


def test_编辑窗口显示人脉关系(app: Any) -> None:
    zhang = app._repo.add_person(Person(display_name='张三'))
    li = app._repo.add_person(Person(display_name='李四'))
    relation_uc.add_relation(
        app._repo,
        person_id=zhang,
        other_id=li,
        kind=RelationKind.FRIEND,
        note='大学同学',
        now=datetime.now(),
    )

    editor_module = pytest.importorskip('rekindle.interfaces.editor')
    editor = editor_module.PersonEditor(app, app._repo, zhang, lambda: None)
    rows = editor._relation_tree.get_children()

    assert len(rows) == 1
    values = editor._relation_tree.item(rows[0], 'values')
    assert values[0] == '李四'
    assert values[1] == '朋友'
    editor.destroy()


def test_编辑窗口可以记录介绍人(app: Any) -> None:
    zhang = app._repo.add_person(Person(display_name='张三'))
    li = app._repo.add_person(Person(display_name='李四'))

    editor_module = pytest.importorskip('rekindle.interfaces.editor')
    editor = editor_module.PersonEditor(app, app._repo, li, lambda: None)
    editor._introducer_var.set(f'张三 (#{zhang})')
    editor._save_introducer()

    relations = app._repo.list_relations(li)
    assert len(relations) == 1
    assert relations[0].kind == RelationKind.INTRODUCED
    assert relations[0].person_a_id == zhang
    assert relations[0].person_b_id == li
    editor.destroy()


def test_关系对话框选择已有联系人(app: Any) -> None:
    dialog_module = pytest.importorskip('rekindle.interfaces.relation_dialog')
    zhang = app._repo.add_person(Person(display_name='张三'))
    li = app._repo.add_person(Person(display_name='李四'))

    dialog = dialog_module.RelationDialog(app, app._repo, zhang, lambda: None)
    dialog._selected_id = li
    dialog._kind.set('同学')
    dialog._save()

    relations = app._repo.list_relations(zhang)
    assert len(relations) == 1
    assert relations[0].kind == RelationKind.CLASSMATE

def test_关系对话框新建联系人(
    app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog_module = pytest.importorskip('rekindle.interfaces.relation_dialog')
    monkeypatch.setattr(
        dialog_module.messagebox, 'showerror', lambda *args, **kwargs: None
    )
    zhang = app._repo.add_person(Person(display_name='张三'))

    dialog = dialog_module.RelationDialog(app, app._repo, zhang, lambda: None)
    dialog._name_var.set('李四')
    dialog._company.set('腾讯')
    dialog._kind.set('同事')
    dialog._save()

    people = {person.display_name: person for person in app._repo.list_people()}
    assert '李四' in people
    li = people['李四'].id or 0
    kinds = {relation.kind for relation in app._repo.list_relations(li)}
    assert kinds == {RelationKind.INTRODUCED, RelationKind.COLLEAGUE}


def test_表单字段由注册表生成(app: Any) -> None:
    # build_grid 返回的键就是字段 key：注册表改了，表单自动跟着变。
    assert list(app._form_widgets) == ['display_name', 'company', 'role']


def test_新建联系人时关系写入失败不会留下半条数据(
    app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog_module = pytest.importorskip('rekindle.interfaces.relation_dialog')
    monkeypatch.setattr(
        dialog_module.messagebox, 'showerror', lambda *args, **kwargs: None
    )

    def boom(*args: object, **kwargs: object) -> int:
        raise InvalidRelation('boom')

    monkeypatch.setattr(dialog_module.relation_uc, 'add_relation', boom)
    zhang = app._repo.add_person(Person(display_name='张三'))

    dialog = dialog_module.RelationDialog(app, app._repo, zhang, lambda: None)
    dialog._name_var.set('李四')
    dialog._save()

    # 关系写入失败 → 同一事务里建的人与介绍关系都要回滚。
    assert [p.display_name for p in app._repo.list_people()] == ['张三']
    assert app._repo.list_relations(zhang) == []
    dialog.destroy()
