'''数量上限：一处定义，模型 / 用例 / 存储 / 界面共用。

这些数字以前散在 8 处（pydantic Field、仓储默认参数、HTTP 校验、GUI 取数），
改一处忘一处就会出现「界面能取 500、API 只收 50」这类不一致。
'''

from __future__ import annotations

# 列表默认返回多少人：queries / 仓储 / HTTP API 的默认值共用。
DEFAULT_LIST_LIMIT = 50

# 一次列表查询允许的上限：界面取数、API 校验共用。
MAX_LIST_LIMIT = 500

# 一句话原文的长度上限：Capture 模型与 HTTP 请求体共用。
RAW_TEXT_MAX_LENGTH = 2000

# 一条交往记录（summary）的长度上限：模型、record、edit 共用。
SUMMARY_MAX_LENGTH = 500
