'''界面输入解析：一个输入框里的多个值。'''

from __future__ import annotations


def split_values(text: str) -> list[str]:
    '''逗号 / 分号 / 顿号分隔，去空白。'''
    for separator in ('，', '；', ';', '、'):
        text = text.replace(separator, ',')
    return [part.strip() for part in text.split(',') if part.strip()]