'''姓氏表：大姓 / 小姓 / 学到的姓；复姓不单独处理。'''

from __future__ import annotations

from rekindle.domain.surnames import surname_length


def test_大姓() -> None:
    assert surname_length('张三') == 1
    assert surname_length('李四') == 1


def test_小姓也算姓() -> None:
    assert surname_length('章三') == 1
    assert surname_length('常联系') == 1


def test_复姓按首字判断() -> None:
    assert surname_length('欧阳娜娜') == 1
    assert surname_length('司马光') == 1


def test_不是姓返回零() -> None:
    assert surname_length('客户') == 0
    assert surname_length('同事') == 0


def test_联系人里的姓也能用() -> None:
    assert surname_length('阿强', {'阿'}) == 1


def test_空字符串返回零() -> None:
    assert surname_length('') == 0
