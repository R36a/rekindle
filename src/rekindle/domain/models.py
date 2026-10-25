'''领域模型（v0.3：只保留「记人」需要的东西）。

产品决策：提醒与待办已移除——只做快速记人、快速查人。
数据库里的旧表/旧列不删除（避免丢数据），但代码不再读写。

这一层只回答两个问题：
1. 数据长什么样 —— 有哪些字段、每个字段是什么类型；
2. 数据必须满足什么规则 —— 哪些必填、长度/范围限制、哪些能是空。

它不碰数据库、不碰网络、不读文件，所以可以单独测试。
'''

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rekindle.domain.relations import RelationKind
from rekindle.domain.text import NAME_MAX_LENGTH


class CaptureStatus(StrEnum):
    '''一条原始输入的三种状态。'''

    DRAFT = 'draft'
    CONFIRMED = 'confirmed'
    DISCARDED = 'discarded'


class ExtractSource(StrEnum):
    '''这次抽取是怎么来的。'''

    RULE = 'rule'
    LLM = 'llm'
    MANUAL = 'manual'


class _StrictModel(BaseModel):
    '''所有领域模型的公共配置：extra=forbid + 自动去首尾空格。'''

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ExtractedFields(_StrictModel):
    '''从一句话里抽出来的字段（规则或 LLM 的产物）。'''

    display_name: str | None = Field(
        default=None, min_length=1, max_length=NAME_MAX_LENGTH
    )
    company: str | None = None
    role: str | None = None
    occurred_at: date | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: ExtractSource = ExtractSource.RULE
    attributes: dict[str, str] = Field(default_factory=dict)  # 自定义字段 key->值

    @field_validator('company', 'role', mode='before')
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        '''把空字符串统一成 None，避免「没有」有三种写法。'''
        if isinstance(value, str) and not value.strip():
            return None
        return value


class Person(_StrictModel):
    '''一个人。'''

    id: int | None = None
    display_name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    pinyin: str = ''
    initials: str = ''
    companies: dict[date, str] = Field(default_factory=dict)  # 日期 -> 公司
    fields: dict[str, list[str]] = Field(default_factory=dict)  # 字段 key -> 多个值
    role: str | None = None
    notes: str | None = None
    last_contact_at: datetime | None = None
    archived: bool = False

    @property
    def current_company(self) -> str | None:
        '''最近一次记录的公司（按日期取最大值）。'''
        if not self.companies:
            return None
        return self.companies[max(self.companies)]


class Alias(_StrictModel):
    '''一个人的另一个叫法。'''

    id: int | None = None
    person_id: int
    text_norm: str = Field(min_length=1, max_length=40)
    source: str = 'user'


class Relation(_StrictModel):
    '''一条人与人之间的关系边。

    六种「认识」关系是对称的，存成 person_a_id < person_b_id；
    introduced 有方向：person_a_id 是介绍人，person_b_id 是被介绍人。
    '''

    id: int | None = None
    person_a_id: int
    person_b_id: int
    kind: RelationKind
    note: str | None = None
    created_at: datetime

    @model_validator(mode='after')
    def _check_endpoints(self) -> Relation:
        if self.person_a_id == self.person_b_id:
            raise ValueError('不能和自己建立关系')
        if (
            self.kind != RelationKind.INTRODUCED
            and self.person_a_id >= self.person_b_id
        ):
            raise ValueError('对称关系必须 person_a_id < person_b_id')
        return self


class Capture(_StrictModel):
    '''一条原始输入。raw_text 就是用户原话本身，只在入口裁掉首尾空白。'''

    id: int | None = None
    raw_text: str = Field(min_length=1, max_length=2000)
    created_at: datetime
    status: CaptureStatus = CaptureStatus.DRAFT
    source: ExtractSource = ExtractSource.RULE
    parsed: ExtractedFields | None = None
    model: str | None = None
    prompt_ver: str | None = None
    person_id: int | None = None


class Interaction(_StrictModel):
    '''一条确认过的交往记录。'''

    id: int | None = None
    person_id: int
    capture_id: int | None = None
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=500)
    created_at: datetime


class Permission(StrEnum):
    '''AI 可以请求的、需要授权的动作（对应 §11.1 的开关）。'''

    ADD_FIELD = 'add_field'
    DELETE_FIELD = 'delete_field'
    AUTO_COMMIT = 'auto_commit'
    SNAPSHOT = 'snapshot'


class PermissionDenied(RuntimeError):
    '''权限不足：对应设置未开启（默认最小权限）。'''

    def __init__(self, perm: Permission) -> None:
        super().__init__(f'权限未开启：{perm.value}（默认最小权限）')
        self.perm = perm


# 快照保留份数：domain 定义，infra 与 Settings 共用（单一来源）。
DEFAULT_SNAPSHOT_KEEP = 10


class Settings(_StrictModel):
    '''用户设置。AI 权限默认最小（全部关闭）。'''

    ai_add_field: bool = False
    ai_delete_field: bool = False
    ai_auto_commit: bool = False
    ai_snapshot: bool = False

    auto_snapshot: bool = True
    auto_snapshot_frequency: str = 'on_exit'   # on_startup / daily / on_exit
    snapshot_keep: int = Field(default=DEFAULT_SNAPSHOT_KEEP, ge=1, le=1000)
    snapshot_dir: str = 'user_data/snapshots'

    def allows(self, perm: Permission) -> bool:
        return bool(getattr(self, 'ai_' + perm.value, False))

    def require(self, perm: Permission) -> None:
        if not self.allows(perm):
            raise PermissionDenied(perm)


class FieldSpec(_StrictModel):
    '''一个可抽取字段的定义（用于生成 LLM 提示词与校验自定义字段）。'''

    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=40)
    field_type: str = 'text'   # text / date / number
    description: str = ''
