'''业务错误的单一来源：infra / app / interfaces 都从这里抛和捕获。

放在 domain 而不是 app，是因为仓储层也要抛「已确认」之类的业务事实，
而依赖方向只允许 interfaces → app → domain ← infra。

接口层的统一边界：可预期的输入错误只有两族——本文件里的 RekindleError，
以及 pydantic 的 ValidationError（它是 ValueError 子类，模型校验失败时抛）。
CLI / GUI 捕获 `(RekindleError, ValueError)`，翻成中文提示 + 退出码/弹窗，
不把回溯直接交给用户。
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


class NameTooLong(RekindleError):
    '''姓名超过模型允许的长度：写库前拦下，避免写进去读不出来。'''

    def __init__(self, limit: int, actual: int) -> None:
        super().__init__(f'姓名太长：最多 {limit} 个字，当前 {actual} 个')
        self.limit = limit
        self.actual = actual


class EmptyCapture(RekindleError):
    '''原话是空白：没有任何可记录的内容。'''

    def __init__(self) -> None:
        super().__init__('原话不能为空：没有可记录的内容')


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
    '''快照版本无法处理：比当前程序新，或太旧、没有逐步迁移路径。'''

    def __init__(self, found: int, expected: int, reason: str = '') -> None:
        detail = f'（{reason}）' if reason else ''
        super().__init__(
            f'快照数据库 v{found} 与当前程序 v{expected} 不兼容{detail}'
        )
        self.found = found
        self.expected = expected


class RelationExists(RekindleError):
    '''同一段关系已经记录过；重复添加不该产生第二行。'''


class RelationNotFound(RekindleError):
    def __init__(self, relation_id: int) -> None:
        super().__init__(f'找不到关系 #{relation_id}')
        self.relation_id = relation_id


class InvalidRelation(RekindleError):
    '''关系类型不合法、指向自己、或两端不存在。'''
