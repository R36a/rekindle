"""领域模型（M1 第一步）。

这一层只回答两个问题：

1. **数据长什么样** —— 有哪些字段、每个字段是什么类型；
2. **数据必须满足什么规则** —— 哪些必填、长度/范围限制、哪些能是空。

它**不碰数据库、不碰网络、不读文件**。

和 Godot 的对照：
    CardResource 里用 `@export var card_capacity : Dictionary` 声明字段，
    这里用 `字段名: 类型 = 默认值` 声明，作用是同一件事，
    区别只是 pydantic 会在**创建对象时立刻校验**，写错了当场报错，
    而不是等到游戏跑起来才崩。
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaptureStatus(str, Enum):
    """一条原始输入的三种状态。

    继承 `str` 是为了让它能直接存进 sqlite（存成 "draft" 这样的字符串），
    同时代码里又能写成 `CaptureStatus.DRAFT` 避免拼写错误。
    """

    DRAFT = "draft"          # 已抽取、等用户确认（默认）
    CONFIRMED = "confirmed"  # 用户点过确认，可以写入 interaction
    DISCARDED = "discarded"  # 用户放弃


class ExtractSource(str, Enum):
    """这次抽取是怎么来的。"""

    RULE = "rule"      # 本地规则（正则/关键词），离线可用
    LLM = "llm"        # 大模型抽取
    MANUAL = "manual"  # 用户手填


class ReminderState(str, Enum):
    """提醒的状态机（设计细节 4.2）。

    注意：`notified` **不允许**回到 `pending`，否则会重复弹窗。
    """

    PENDING = "pending"    # 等待触发
    NOTIFIED = "notified"  # 已经弹过（关键：写过就不再弹）
    DONE = "done"          # 用户已完成
    SNOOZED = "snoozed"    # 延后几天
    MUTED = "muted"        # 静音此人


class _StrictModel(BaseModel):
    """所有领域模型的公共配置。

    `extra="forbid"`：多传一个字段直接报错。
        好处是拼写错误（写成 `compnay`）不会被静默忽略。
    `str_strip_whitespace=True`：字符串自动去掉首尾空格。
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExtractedFields(_StrictModel):
    """从一句话里抽出来的字段（规则或 LLM 的产物）。

    这是"还没进数据库"的中间结果，所以字段都比较宽松（允许 None）。
    """

    display_name: str = Field(min_length=1, max_length=20)
    company: str | None = None
    role: str | None = None
    occurred_at: date | None = None      # 只要日期，"几点"由系统补
    promise: str | None = None           # 例："帮我看简历"
    cadence_days: int | None = Field(default=None, ge=1, le=365)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: ExtractSource = ExtractSource.RULE

    @field_validator("company", "role", "promise", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        """把空字符串统一成 None。

        否则数据库里会同时出现 ""、None、"  " 三种"没有"，
        后面判断"有没有公司"时要写三个条件，很容易漏。
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value


class Person(_StrictModel):
    """一个人。"""

    id: int | None = None                # None = 还没入库，由数据库分配
    display_name: str = Field(min_length=1, max_length=20)
    pinyin: str = ""                     # 全拼，消歧用（第二阶段才填）
    initials: str = ""                   # 首字母，消歧用
    company: str | None = None
    role: str | None = None
    notes: str | None = None
    cadence_days: int | None = Field(default=None, ge=1, le=365)
    last_contact_at: datetime | None = None
    next_due_at: datetime | None = None
    archived: bool = False               # 归档而不是删除（不丢数据）


class Alias(_StrictModel):
    """一个人的另一个叫法，例如"张总""张三老师"。

    `text_norm` 是归一化之后的写法（去空格、统一大小写），
    数据库会对 (person_id, text_norm) 建唯一索引，防止重复。
    """

    id: int | None = None
    person_id: int
    text_norm: str = Field(min_length=1, max_length=40)
    source: str = "user"


class Capture(_StrictModel):
    """一条原始输入。

    `raw_text` 永远保存用户原话，**不改写**——
    以后想换更好的抽取算法时，可以拿原始文本重跑一遍。
    """

    id: int | None = None
    raw_text: str = Field(min_length=1, max_length=2000)
    created_at: datetime
    status: CaptureStatus = CaptureStatus.DRAFT
    source: ExtractSource = ExtractSource.RULE
    parsed: ExtractedFields | None = None
    model: str | None = None             # 用了哪个模型（离线时为 None）
    prompt_ver: str | None = None        # prompt 版本，便于对比效果
    person_id: int | None = None         # 确认后回填


class Interaction(_StrictModel):
    """一条确认过的交往记录。

    只有用户点了"确认"才会创建它——这是"容错优先于全自动"的物理保证。
    """

    id: int | None = None
    person_id: int
    capture_id: int | None = None        # 数据库里有 UNIQUE 约束，防重复入库
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=500)
    promise: str | None = None
    created_at: datetime


class Reminder(_StrictModel):
    """一条提醒。"""

    id: int | None = None
    person_id: int
    due_at: datetime
    reason: str = "到期"
    state: ReminderState = ReminderState.PENDING
    notified_at: datetime | None = None  # 弹过的时刻（幂等的关键）
    snooze_until: datetime | None = None
    created_at: datetime
