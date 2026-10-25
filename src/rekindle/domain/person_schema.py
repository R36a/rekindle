'''人员字段注册表：全项目唯一的「字段定义」来源。

一个字段在这里声明一次（key / 标签 / 存储方式 / 约束 / 是否可搜 / 是否进摘要 / CLI 开关），
下面这些地方全部由它派生，不再各写一遍：

| 派生目标 | 生成者 |
|---|---|
| `person` 表的 DDL（列名、类型、NOT NULL、默认值） | `infra/schema_sql.py` |
| 搜索 SQL（哪些列参与 LIKE） | `infra/sqlite_repo.SqliteRepo.list_people` |
| 「用户输入了：…」摘要的字段与顺序 | `app/record._manual_summary` |
| `--name / --company / --role / --wechat …` 参数 | `interfaces/cli._add_person_arguments` |
| 表单里的标签文案、输入框宽度、多行/单行 | `interfaces/forms.build_grid` |

**故意不生成**（写在这里避免下次有人再问）：
- **迁移脚本**：项目不做逐版本迁移（版本不符直接重建），所以没有「从注册表重算
  历史步骤」的问题；当前表的形状仍由本文件生成，schema 不再是手写 DDL。
- **API 出入参**：那是对外契约（`name` vs `display_name` 的别名、必填规则不同），
  且 `mypy --strict` 需要静态类型，动态 `create_model` 会让类型检查失效。
'''

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rekindle.domain.fields import DEFAULT_FIELDS
from rekindle.domain.text import NAME_MAX_LENGTH


class Storage(StrEnum):
    '''这个字段存在哪张表。'''

    COLUMN = 'column'    # person 表的列
    COMPANY = 'company'  # person_company：按日期累积的历史
    CONTACT = 'contact'  # person_field：可追加多个值的键值行


class Widget(StrEnum):
    '''表单里用什么控件；NONE = 不进表单。'''

    NONE = 'none'
    ENTRY = 'entry'
    TEXT = 'text'


@dataclass(frozen=True)
class PersonField:
    key: str
    label: str
    storage: Storage
    # ---- 用于生成 person 表的 DDL（只有 COLUMN 用得到）----
    sql_type: str = ''
    sql_default: str | None = None
    not_null: bool = False
    primary_key: bool = False
    # ---- 用途 ----
    max_length: int | None = None
    searchable: bool = False
    summary_order: int | None = None   # 进摘要的字段，按此排序
    cli_flag: str = ''                 # CLI 参数名（不含 --）；空则用 key
    cli_help: str = ''                 # CLI 帮助文案；空则用 label

    # ---- 表单 ----
    widget: Widget = Widget.ENTRY
    width: int = 20

    @property
    def in_summary(self) -> bool:
        return self.summary_order is not None

    @property
    def editable(self) -> bool:
        return self.widget is not Widget.NONE

    @property
    def flag(self) -> str:
        return self.cli_flag or self.key

    @property
    def in_cli(self) -> bool:
        return bool(self.cli_flag)


PERSON_FIELDS: tuple[PersonField, ...] = (
    # —— person 表的列：顺序即 DDL 顺序 ——
    PersonField('id', 'ID', Storage.COLUMN, 'INTEGER',
                primary_key=True, widget=Widget.NONE),
    PersonField('display_name', '姓名', Storage.COLUMN, 'TEXT',
                not_null=True, max_length=NAME_MAX_LENGTH, searchable=True,
                summary_order=0, cli_flag='name', cli_help='姓名（抽不到时必填）',
                width=26),
    PersonField('role', '职位', Storage.COLUMN, 'TEXT',
                searchable=True, summary_order=2, cli_flag='role', width=26),
    PersonField('notes', '备注', Storage.COLUMN, 'TEXT',
                searchable=True, widget=Widget.TEXT, width=40),
    PersonField('last_contact_at', '最近联系', Storage.COLUMN, 'TEXT',
                widget=Widget.NONE),
    PersonField('archived', '已归档', Storage.COLUMN, 'INTEGER',
                not_null=True, sql_default='0', widget=Widget.NONE),
    # —— 公司：按日期累积的历史，不进 person 表 ——
    PersonField('company', '公司', Storage.COMPANY,
                searchable=True, summary_order=1, cli_flag='company', width=26),
    # —— 联系方式：person_field 键值行，清单来自 DEFAULT_FIELDS ——
    *(
        PersonField(spec.key, spec.label, Storage.CONTACT,
                    searchable=True, summary_order=3 + index,
                    cli_flag=spec.key, width=24)
        for index, spec in enumerate(DEFAULT_FIELDS)
    ),
)

FIELD_BY_KEY: dict[str, PersonField] = {field.key: field for field in PERSON_FIELDS}

# 以下都是同一份 PERSON_FIELDS 的投影，不新增事实。
COLUMN_FIELDS: tuple[PersonField, ...] = tuple(
    field for field in PERSON_FIELDS if field.storage is Storage.COLUMN
)
SEARCHABLE_FIELDS: tuple[PersonField, ...] = tuple(
    field for field in PERSON_FIELDS if field.searchable
)
SUMMARY_FIELDS: tuple[PersonField, ...] = tuple(
    sorted(
        (field for field in PERSON_FIELDS if field.in_summary),
        key=lambda field: field.summary_order or 0,
    )
)
CLI_FIELDS: tuple[PersonField, ...] = tuple(
    field for field in PERSON_FIELDS if field.in_cli
)
FORM_FIELDS: tuple[PersonField, ...] = tuple(
    field for field in PERSON_FIELDS if field.editable
)
CONTACT_FIELDS: tuple[PersonField, ...] = tuple(
    field for field in PERSON_FIELDS if field.storage is Storage.CONTACT
)
CONTACT_KEYS: tuple[str, ...] = tuple(field.key for field in CONTACT_FIELDS)
