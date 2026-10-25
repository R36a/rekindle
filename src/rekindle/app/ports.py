'''端口（开发文档 §5.2 的 seam）。

app 只认这里的协议；唯一实现是 infra/sqlite_repo.py，测试也用真实临时 sqlite。

以前按用例拆成 5 个 Protocol（RecordPort / QueryPort / EditPort / BackupPort /
RelationPort），每个都把 `get_person`、`update_person`、`list_interactions` 的签名
再抄一遍：改一个签名要改 4 处，而替代实现始终是 0 个。现在收敛成一个 `Repo`。
方法宁可少一点，也不要为「以后可能用到」提前加。
'''

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol

from rekindle.domain.limits import DEFAULT_LIST_LIMIT
from rekindle.domain.models import (
    Capture,
    ExtractedFields,
    Interaction,
    Person,
    Relation,
)


class Repo(Protocol):
    '''app 层需要的全部存储能力：读写人、记录、关系与整库备份。'''

    def transaction(self) -> AbstractContextManager[None]:
        '''把多个写操作合成一个事务；**不可嵌套**（最外层用这个）。'''
        ...

    def atomic(self) -> AbstractContextManager[None]:
        '''可嵌套的事务：已在事务里就复用外层，否则自己开一个。'''
        ...

    # ---------- 原始输入 ----------
    def add_capture(
        self, raw_text: str, created_at: datetime, parsed: ExtractedFields
    ) -> int: ...

    def get_capture(self, capture_id: int) -> Capture | None: ...

    def confirm_capture(self, capture_id: int, person_id: int) -> None: ...

    # ---------- 人 ----------
    def find_person_by_alias(self, text: str) -> Person | None: ...

    def find_person_by_name(self, name: str) -> Person | None: ...

    def get_person(self, person_id: int) -> Person | None: ...

    def add_person(self, person: Person) -> int: ...

    def update_person(self, person: Person) -> None: ...

    def archive_person(self, person_id: int) -> None: ...

    def list_people(
        self, query: str = '', limit: int = DEFAULT_LIST_LIMIT
    ) -> list[Person]: ...

    def list_person_names(self) -> list[str]:
        '''所有未归档人的姓名，用来学习罕见姓氏。'''
        ...

    # ---------- 交往记录 ----------
    def add_interaction(self, interaction: Interaction) -> int: ...

    def list_interactions(self, person_id: int) -> list[Interaction]: ...

    def update_interaction(self, interaction: Interaction) -> None: ...

    def delete_interaction(self, interaction_id: int) -> None: ...

    # ---------- 关系 ----------
    def add_relation(self, relation: Relation) -> int: ...

    def delete_relation(self, relation_id: int) -> None: ...

    # ---------- 备份 ----------
    def export_all(self) -> dict[str, list[dict[str, object]]]: ...

    def import_all(self, tables: dict[str, list[dict[str, object]]]) -> None: ...

