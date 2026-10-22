'''称呼归一化：消歧与别名匹配的唯一口径。

规则：全角转半角(NFKC) → 去空白 → 小写 → 去掉常见敬称后缀。
「张总」「张 总 」和「张」在匹配时视为同一个键。
'''

from __future__ import annotations

import unicodedata

# 只去掉明确的敬称后缀；不做模糊音、不做编辑距离（原型阶段宁可多建，不可错并）。
_HONORIFICS = ('老师', '总', '工')


def normalize_name(text: str) -> str:
    s = unicodedata.normalize('NFKC', text)
    s = ''.join(s.split()).lower()
    for suffix in _HONORIFICS:
        if len(s) > len(suffix) and s.endswith(suffix):
            return s[: -len(suffix)]
    return s
