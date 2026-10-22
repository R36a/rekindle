'''称呼归一化：消歧匹配的唯一口径。'''

from __future__ import annotations

from rekindle.domain.normalize import normalize_name


def test_去掉敬称后缀() -> None:
    assert normalize_name('张总') == '张'
    assert normalize_name('李老师') == '李'


def test_去掉空白与统一全角() -> None:
    assert normalize_name(' 张 三 ') == '张三'
    assert normalize_name('ＡＢＣ') == 'abc'


def test_短名字不误删() -> None:
    assert normalize_name('王工') == '王'
    assert normalize_name('工') == '工'
