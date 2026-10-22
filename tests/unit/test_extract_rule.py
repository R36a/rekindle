'''规则抽取的测试：固定 today，逐字段断言。'''

from __future__ import annotations

from datetime import date

from rekindle.domain.extract_rule import extract

TODAY = date(2026, 10, 21)


def test_姓名_和张三() -> None:
    assert extract('和张三吃饭', TODAY).display_name == '张三'


def test_姓名_认识李四() -> None:
    assert extract('认识了李四', TODAY).display_name == '李四'


def test_姓名_复姓四个字() -> None:
    assert extract('认识欧阳娜娜', TODAY).display_name == '欧阳娜娜'


def test_姓名_抽不到() -> None:
    assert extract('今天天气不错', TODAY).display_name is None


def test_姓名_不是姓氏会被拒绝() -> None:
    assert extract('跟客户开会', TODAY).display_name is None


def test_姓名_两个名字只取第一个() -> None:
    assert extract('和张三李四吃饭', TODAY).display_name == '张三'


def test_姓名_三字名() -> None:
    assert extract('和杨小明吃饭', TODAY).display_name == '杨小明'


def test_姓名_复姓带名() -> None:
    assert extract('和司马光吃饭', TODAY).display_name == '司马光'


def test_姓名_没有提示词也能扫到() -> None:
    assert extract('张三在吃饭', TODAY).display_name == '张三'
    assert extract('今天张三在吃饭', TODAY).display_name == '张三'
    assert extract('李四是产品经理', TODAY).display_name == '李四'


def test_姓名_已知姓名优先() -> None:
    assert extract('和公皙明吃饭', TODAY, ['公皙明']).display_name == '公皙明'


def test_姓名_没学过的罕见姓会被拒绝() -> None:
    assert extract('和公皙明吃饭', TODAY).display_name is None


def test_姓名_误判优于漏判() -> None:
    assert extract('常联系', TODAY).display_name == '常联系'


def test_姓名_于是不当人名() -> None:
    assert extract('于是我们聊了聊', TODAY).display_name is None


def test_公司_在X工作() -> None:
    assert extract('上周在字节工作', TODAY).company == '字节'


def test_公司_腾讯公司() -> None:
    assert extract('腾讯公司的张三', TODAY).company == '腾讯'


def test_职位_做后端() -> None:
    assert extract('他做后端', TODAY).role == '后端'


def test_职位_抽不到() -> None:
    assert extract('他人很好', TODAY).role is None


def test_时间_昨天() -> None:
    assert extract('昨天见面', TODAY).occurred_at == date(2026, 10, 20)


def test_时间_前天() -> None:
    assert extract('前天见面', TODAY).occurred_at == date(2026, 10, 19)


def test_时间_上周() -> None:
    assert extract('上周见面', TODAY).occurred_at == date(2026, 10, 14)


def test_时间_下周() -> None:
    assert extract('下周见面', TODAY).occurred_at == date(2026, 10, 28)


def test_时间_抽不到() -> None:
    assert extract('随便聊聊', TODAY).occurred_at is None


def test_综合_一句话全抽() -> None:
    result = extract('上周和张三在字节工作，他做后端', TODAY)

    assert result.display_name == '张三'
    assert result.company == '字节'
    assert result.role == '后端'
    assert result.occurred_at == date(2026, 10, 14)
