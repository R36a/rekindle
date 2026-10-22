'''用例层：只依赖 domain 与下方端口，不 import sqlite / httpx。

这样 CLI、GUI、测试都能用同一套用例，换存储不影响业务规则。
'''

from __future__ import annotations
