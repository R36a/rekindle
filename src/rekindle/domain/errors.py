'''业务错误的单一来源：infra / app / interfaces 都从这里抛和捕获。

放在 domain 而不是 app，是因为仓储层也要抛「已确认」之类的业务事实，
而依赖方向只允许 interfaces → app → domain ← infra。
'''

from __future__ import annotations


class RekindleError(RuntimeError):
    '''本项目所有可预期错误的基类：调用方捕获它即可给出中文提示。'''


class CaptureNotFound(RekindleError):
    def __init__(self, capture_id: int) -> None:
        super().__init__(f'找不到草稿 capture #{capture_id}')
        self.capture_id = capture_id


class AlreadyConfirmed(RekindleError):
    def __init__(self, capture_id: int) -> None:
        super().__init__(f'capture #{capture_id} 已确认或已丢弃，不会重复入库')
        self.capture_id = capture_id


class MissingName(RekindleError):
    '''姓名是唯一必需字段：抽不到且用户没给 → 不写库。'''


class PersonNotFound(RekindleError):
    def __init__(self, person_id: int) -> None:
        super().__init__(f'找不到 person #{person_id}')
        self.person_id = person_id


class ImportTargetNotEmpty(RekindleError):
    '''导入只允许写空库，避免主键撞车或悄悄覆盖现有数据。'''


class BackupFormatError(RekindleError):
    '''导出文件不是本项目的格式，或版本不认识。'''

class SnapshotError(RekindleError):
    '''快照读取或恢复失败。'''


class SnapshotVersionMismatch(SnapshotError):
    def __init__(self, found: int, expected: int) -> None:
        super().__init__(
            f'快照数据库版本 v{found} 与当前程序 v{expected} 不一致，请用对应版本恢复'
        )
        self.found = found
        self.expected = expected