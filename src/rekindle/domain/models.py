'''领域模型（M1 第一步，T3 更新）。

这一层只回答两个问题：
1. 数据长什么样 —— 有哪些字段、每个字段是什么类型；
2. 数据必须满足什么规则 —— 哪些必填、长度/范围限制、哪些能是空。

它不碰数据库、不碰网络、不读文件，所以可以单独测试。

注意：本文件统一用单引号字符串（不用双引号），
因为当前写文件走 PowerShell here-string，双引号与外壳转义冲突。
'''

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaptureStatus(str, Enum):
    '''一条原始输入的三种状态。'''

    DRAFT = 'draft'
    CONFIRMED = 'confirmed'
    DISCARDED = 'discarded'


class ExtractSource(str, Enum):
    '''这次抽取是怎么来的。'''

    RULE = 'rule'
    LLM = 'llm'
    MANUAL = 'manual'


class ReminderState(str, Enum):
    '''提醒的状态机。notified 不允许回到 pending，否则会重复弹窗。'''

    PENDING = 'pending'
    NOTIFIED = 'notified'
    DONE = 'done'
    SNOOZED = 'snoozed'
    MUTED = 'muted'


class RepeatRule(str, Enum):
    '''待办的重复规则。none = 不重复。'''

    NONE = 'none'
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'
    CUSTOM = 'custom'


class _StrictModel(BaseModel):
    '''所有领域模型的公共配置：extra=forbid + 自动去首尾空格。'''

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class TodoDraft(_StrictModel):
    '''从一句话里抽出来的待办草稿（还没确认、还没入库）。

    与 docs/设计细节.md §10 的 Todo 实体不同：这里是抽取的中间结果，
    涉及的人还是姓名字符串，而不是 person_id。
    '''

    title: str = Field(min_length=1, max_length=200)
    due_on: date | None = None
    repeat_rule: RepeatRule = RepeatRule.NONE
    people_names: list[str] = Field(default_factory=list)


class ExtractedFields(_StrictModel):
    '''从一句话里抽出来的字段（规则或 LLM 的产物）。'''

    display_name: str | None = Field(default=None, min_length=1, max_length=20)
    company: str | None = None
    role: str | None = None
    occurred_at: date | None = None
    cadence_days: int | None = Field(default=None, ge=1, le=365)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: ExtractSource = ExtractSource.RULE
    todos: list[TodoDraft] = Field(default_factory=list)

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
    display_name: str = Field(min_length=1, max_length=20)
    pinyin: str = ''
    initials: str = ''
    company: str | None = None
    role: str | None = None
    notes: str | None = None
    cadence_days: int | None = Field(default=None, ge=1, le=365)
    last_contact_at: datetime | None = None
    next_due_at: datetime | None = None
    archived: bool = False


class Alias(_StrictModel):
    '''一个人的另一个叫法。'''

    id: int | None = None
    person_id: int
    text_norm: str = Field(min_length=1, max_length=40)
    source: str = 'user'


class Capture(_StrictModel):
    '''一条原始输入。raw_text 永远保存用户原话，不改写。'''

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
    '''一条确认过的交往记录。

    注：promise 字段即将被 Todo 实体取代（见 §10），暂留待迁移。
    '''

    id: int | None = None
    person_id: int
    capture_id: int | None = None
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=500)
    promise: str | None = None
    created_at: datetime


class Reminder(_StrictModel):
    '''一条提醒。'''

    id: int | None = None
    person_id: int
    due_at: datetime
    reason: str = '到期'
    state: ReminderState = ReminderState.PENDING
    notified_at: datetime | None = None
    snooze_until: datetime | None = None
    created_at: datetime
