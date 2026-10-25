'''由字段注册表生成 SQL：`person` 表的形状不再手写。

**分工**：
- 当前形状（列名/类型/NOT NULL/默认值）← `domain/person_schema.COLUMN_FIELDS`
- 版本不一致直接重建（`sqlite_repo._migrate`），没有历史步骤要维护

这样「加一个 person 列」= 注册表加一项，不会再出现
"模型有、DDL 没有"或反过来的漂移。
'''

from __future__ import annotations

from rekindle.domain.person_schema import COLUMN_FIELDS, PersonField

_NAME_WIDTH = 16


def _column_sql(field: PersonField) -> str:
    parts = [f'{field.key:<{_NAME_WIDTH}}{field.sql_type}']
    if field.primary_key:
        parts.append('PRIMARY KEY')
    if field.not_null:
        parts.append('NOT NULL')
    if field.sql_default is not None:
        parts.append(f'DEFAULT {field.sql_default}')
    return ' '.join(parts)


def person_table_sql() -> str:
    '''person 表 DDL：列与约束全部来自注册表，顺序即声明顺序。'''
    columns = ',\n'.join(f'    {_column_sql(field)}' for field in COLUMN_FIELDS)
    return f'CREATE TABLE person (\n{columns}\n    )'
