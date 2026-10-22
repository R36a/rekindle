'''端口（开发文档 §5.2 的 seam）。

app 只认这里的协议；真实实现是 infra/sqlite_repo.py，测试里用临时 sqlite。
方法宁可少一点，也不要为「以后可能用到」提前加。
'''

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol

from rekindle.domain.models import Capture, ExtractedFields, Interaction, Person


class RecordPort(Protocol):
    '''写入一条记录所需的全部存储操作。'''

    def transaction(self) -> AbstractContextManager[None]:
        '''把多个写操作合成一个事务；不可嵌套。'''
        ...

    def add_capture(
        self, raw_text: str, created_at: datetime, parsed: ExtractedFields
    ) -> int: ...

    def get_capture(self, capture_id: int) -> Capture | None: ...

    def confirm_capture(self, capture_id: int, person_id: int) -> None: ...

    def discard_capture(self, capture_id: int) -> None: ...

    def find_person_by_alias(self, text: str) -> Person | None: ...

    def find_person_by_name(self, name: str) -> Person | None: ...

    def get_person(self, person_id: int) -> Person | None: ...

    def add_person(self, person: Person) -> int: ...

    def update_person(self, person: Person) -> None: ...

    def add_alias(self, person_id: int, text: str) -> None: ...

    def add_interaction(self, interaction: Interaction) -> int: ...

    def list_person_names(self) -> list[str]:
        '''所有未归档人的姓名，用来学习罕见姓氏。'''
        ...


class QueryPort(Protocol):
    '''只读查询。'''

    def get_person(self, person_id: int) -> Person | None: ...

    def list_people(self, query: str = '', limit: int = 50) -> list[Person]: ...

    def list_interactions(self, person_id: int) -> list[Interaction]: ...


class BackupPort(Protocol):
    '''整库导出 / 导入（JSON 是权威备份格式）。'''

    def export_all(self) -> dict[str, list[dict[str, object]]]: ...

    def import_all(self, tables: dict[str, list[dict[str, object]]]) -> None: ...
