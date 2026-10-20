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


def test_联系间隔_常联系() -> None:
    assert extract('以后常联系', TODAY).cadence_days == 30


def test_联系间隔_每周() -> None:
    assert extract('每周碰一次', TODAY).cadence_days == 7


def test_联系间隔_抽不到() -> None:
    assert extract('再见', TODAY).cadence_days is None


def test_待办_答应帮我下周看简历() -> None:
    result = extract('答应帮我下周看简历', TODAY)
    assert len(result.todos) == 1
    assert '看简历' in result.todos[0].title
    assert result.todos[0].due_on == date(2026, 10, 28)


def test_待办_说好一起吃饭() -> None:
    result = extract('说好一起吃饭', TODAY)
    assert len(result.todos) == 1
    assert result.todos[0].title == '一起吃饭'


def test_待办_无触发词() -> None:
    assert extract('今天天气不错', TODAY).todos == []


def test_综合_一句话全抽() -> None:
    result = extract('上周和张三在字节工作，他做后端，答应帮我下周看简历', TODAY)
    assert result.display_name == '张三'
    assert result.company == '字节'
    assert result.role == '后端'
    assert result.occurred_at == date(2026, 10, 14)
    assert len(result.todos) == 1
    assert result.todos[0].people_names == ['张三']
