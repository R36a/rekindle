'''字段清洗口径：一处定义「有值 / None」「姓名合法」这两件事。

之前 record / edit / GUI / 关系对话框各写了一遍 `(text or '').strip() or None`，
导致「 腾讯 」经 confirm 会带空格入库，而 manual 会被清掉。统一到这里。
'''

from __future__ import annotations

from rekindle.domain.errors import MissingName, NameTooLong

# 姓名长度上限：models.Person / models.ExtractedFields 与 require_name 共用这一个数。
NAME_MAX_LENGTH = 20


def clean_optional(text: str | None) -> str | None:
    '''去掉首尾空白；空串 / 全空白 / None 一律返回 None。'''
    if text is None:
        return None
    cleaned = text.strip()
    return cleaned or None


def require_name(value: str | None) -> str:
    '''校验并返回合法姓名：去空白、拒绝空、拒绝超长。

    record（原话入库 / 手动入库）与 edit（改资料）都走这一个函数。
    以前只在 pydantic 模型里约束长度，而 `model_copy(update=...)` 不跑校验，
    于是编辑时能写进超长姓名，读出来才报错——现在写库前就拦住。
    '''
    name = (value or '').strip()
    if not name:
        raise MissingName('缺少姓名：姓名是必填字段')
    if len(name) > NAME_MAX_LENGTH:
        raise NameTooLong(NAME_MAX_LENGTH, len(name))
    return name
