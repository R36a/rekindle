'''SQLite 仓储：本项目唯一的持久化实现（ADR-001 单文件）。

v0.3 只存「人 / 别名 / 原始输入 / 交往记录」：提醒与待办按产品决策移除。
旧库（v1）打开时直接重建：开发期数据按用户要求丢弃，不做兼容迁移。
'''

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from rekindle.domain.errors import (
    AlreadyConfirmed,
    BackupFormatError,
    ImportTargetNotEmpty,
)
from rekindle.domain.models import (
    Capture,
    CaptureStatus,
    ExtractedFields,
    ExtractSource,
    Interaction,
    Person,
)
from rekindle.domain.normalize import normalize_name

SCHEMA_VERSION = 3

_SCHEMA = (
    '''
    CREATE TABLE person (
        id              INTEGER PRIMARY KEY,
        display_name    TEXT    NOT NULL,
        pinyin          TEXT    NOT NULL DEFAULT '',
        initials        TEXT    NOT NULL DEFAULT '',
        role            TEXT,
        notes           TEXT,
        last_contact_at TEXT,
        archived        INTEGER NOT NULL DEFAULT 0
    )
    ''',
    '''
    CREATE TABLE person_company (
        person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
        on_date   TEXT    NOT NULL,
        company   TEXT    NOT NULL,
        PRIMARY KEY (person_id, on_date)
    )
    ''',
    'CREATE INDEX ix_person_company_name ON person_company(company)',
    '''
    CREATE TABLE alias (
        id        INTEGER PRIMARY KEY,
        person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
        text_norm TEXT    NOT NULL,
        source    TEXT    NOT NULL DEFAULT 'user'
    )
    ''',
    'CREATE UNIQUE INDEX ux_alias_person_text ON alias(person_id, text_norm)',
    'CREATE INDEX ix_alias_text ON alias(text_norm)',
    '''
    CREATE TABLE capture (
        id          INTEGER PRIMARY KEY,
        raw_text    TEXT    NOT NULL,
        created_at  TEXT    NOT NULL,
        status      TEXT    NOT NULL,
        source      TEXT    NOT NULL,
        parsed_json TEXT,
        model       TEXT,
        prompt_ver  TEXT,
        person_id   INTEGER REFERENCES person(id)
    )
    ''',
    '''
    CREATE TABLE interaction (
        id          INTEGER PRIMARY KEY,
        person_id   INTEGER NOT NULL REFERENCES person(id),
        capture_id  INTEGER UNIQUE REFERENCES capture(id),
        occurred_at TEXT    NOT NULL,
        summary     TEXT    NOT NULL,
        created_at  TEXT    NOT NULL
    )
    ''',
    'CREATE INDEX ix_interaction_person_time ON interaction(person_id, occurred_at DESC)',
)

# 导出顺序 = 外键的父 → 子；导入按同样顺序插入。
_TABLES = ('person', 'alias', 'capture', 'interaction', 'person_company')

# 旧结构（v1）里多出来的表；删表按子 → 父。
_LEGACY_TABLES = (
    'person_company',
    'todo_person',
    'todo',
    'interaction',
    'capture',
    'alias',
    'person',
)


def _dt(value: object) -> datetime | None:
    return datetime.fromisoformat(str(value)) if value else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _person(row: sqlite3.Row, companies: dict[date, str]) -> Person:
    return Person(
        id=row['id'],
        display_name=row['display_name'],
        pinyin=row['pinyin'],
        initials=row['initials'],
        companies=companies,
        role=row['role'],
        notes=row['notes'],
        last_contact_at=_dt(row['last_contact_at']),
        archived=bool(row['archived']),
    )


def _capture(row: sqlite3.Row) -> Capture:
    raw = row['parsed_json']
    return Capture(
        id=row['id'],
        raw_text=row['raw_text'],
        created_at=datetime.fromisoformat(row['created_at']),
        status=CaptureStatus(row['status']),
        source=ExtractSource(row['source']),
        parsed=ExtractedFields.model_validate_json(raw) if raw else None,
        model=row['model'],
        prompt_ver=row['prompt_ver'],
        person_id=row['person_id'],
    )


def _interaction(row: sqlite3.Row) -> Interaction:
    return Interaction(
        id=row['id'],
        person_id=row['person_id'],
        capture_id=row['capture_id'],
        occurred_at=datetime.fromisoformat(row['occurred_at']),
        summary=row['summary'],
        created_at=datetime.fromisoformat(row['created_at']),
    )


class SqliteRepo:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(self.path) != ':memory:':
            self.path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None = 自动提交，事务由下面的 transaction() 显式管理。
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute('PRAGMA foreign_keys = ON')
        if str(self.path) != ':memory:':
            self._conn.execute('PRAGMA journal_mode = WAL')
        self._migrate()

    def __enter__(self) -> SqliteRepo:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    @property
    def schema_version(self) -> int:
        return int(self._conn.execute('PRAGMA user_version').fetchone()[0])

    def _migrate(self) -> None:
        version = self.schema_version
        if version == SCHEMA_VERSION:
            return
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f'数据库版本 {version} 高于程序支持的 {SCHEMA_VERSION}，请升级 rekindle'
            )
        with self.transaction():
            if version:
                for table in _LEGACY_TABLES:
                    self._conn.execute(f'DROP TABLE IF EXISTS {table}')
            for statement in _SCHEMA:
                self._conn.execute(statement)
            self._conn.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')

    @contextmanager
    def transaction(self) -> Iterator[None]:
        '''显式事务；不支持嵌套（内层请用 _atomic）。'''
        if self._conn.in_transaction:
            raise RuntimeError('不支持嵌套事务')
        self._conn.execute('BEGIN')
        try:
            yield
        except BaseException:
            self._conn.execute('ROLLBACK')
            raise
        else:
            self._conn.execute('COMMIT')

    @contextmanager
    def _atomic(self) -> Iterator[None]:
        '''已经在事务里就复用外层，否则自己开一个。'''
        if self._conn.in_transaction:
            yield
        else:
            with self.transaction():
                yield

    # ---------- capture ----------

    def add_capture(
        self, raw_text: str, created_at: datetime, parsed: ExtractedFields
    ) -> int:
        cur = self._conn.execute(
            'INSERT INTO capture (raw_text, created_at, status, source, parsed_json) '
            'VALUES (?, ?, ?, ?, ?)',
            (
                raw_text,
                created_at.isoformat(),
                CaptureStatus.DRAFT.value,
                parsed.source.value,
                parsed.model_dump_json(),
            ),
        )
        return int(cur.lastrowid or 0)

    def get_capture(self, capture_id: int) -> Capture | None:
        row = self._conn.execute(
            'SELECT * FROM capture WHERE id = ?', (capture_id,)
        ).fetchone()
        return _capture(row) if row else None

    def confirm_capture(self, capture_id: int, person_id: int) -> None:
        cur = self._conn.execute(
            'UPDATE capture SET status = ?, person_id = ? WHERE id = ? AND status = ?',
            (
                CaptureStatus.CONFIRMED.value,
                person_id,
                capture_id,
                CaptureStatus.DRAFT.value,
            ),
        )
        # 影响 0 行 = 状态已被别处改过（重复确认/已丢弃），必须让上层知道。
        if cur.rowcount == 0:
            raise AlreadyConfirmed(capture_id)

    def discard_capture(self, capture_id: int) -> None:
        cur = self._conn.execute(
            'UPDATE capture SET status = ? WHERE id = ? AND status = ?',
            (CaptureStatus.DISCARDED.value, capture_id, CaptureStatus.DRAFT.value),
        )
        if cur.rowcount == 0:
            raise AlreadyConfirmed(capture_id)

    # ---------- person / alias ----------

    def find_person_by_alias(self, text: str) -> Person | None:
        row = self._conn.execute(
            'SELECT p.* FROM alias a JOIN person p ON p.id = a.person_id '
            'WHERE a.text_norm = ? AND p.archived = 0 LIMIT 1',
            (normalize_name(text),),
        ).fetchone()
        return self._load_person(row) if row else None

    def find_person_by_name(self, name: str) -> Person | None:
        row = self._conn.execute(
            'SELECT * FROM person WHERE display_name = ? AND archived = 0 '
            'ORDER BY id LIMIT 1',
            (name,),
        ).fetchone()
        return self._load_person(row) if row else None

    def get_person(self, person_id: int) -> Person | None:
        row = self._conn.execute(
            'SELECT * FROM person WHERE id = ?', (person_id,)
        ).fetchone()
        return self._load_person(row) if row else None

    def _replace_companies(self, person_id: int, companies: dict[date, str]) -> None:
        '''整体替换某人的公司历史（数据量小，简单胜过增量）。'''
        self._conn.execute(
            'DELETE FROM person_company WHERE person_id = ?', (person_id,)
        )
        for on_date, company in companies.items():
            self._conn.execute(
                'INSERT INTO person_company (person_id, on_date, company) '
                'VALUES (?, ?, ?)',
                (person_id, on_date.isoformat(), company),
            )

    def _companies_of(self, person_id: int) -> dict[date, str]:
        rows = self._conn.execute(
            'SELECT on_date, company FROM person_company WHERE person_id = ? '
            'ORDER BY on_date',
            (person_id,),
        ).fetchall()
        return {
            date.fromisoformat(str(row['on_date'])): str(row['company'])
            for row in rows
        }

    def _companies_for(self, person_ids: list[int]) -> dict[int, dict[date, str]]:
        if not person_ids:
            return {}
        placeholders = ', '.join('?' for _ in person_ids)
        rows = self._conn.execute(
            f'SELECT person_id, on_date, company FROM person_company '
            f'WHERE person_id IN ({placeholders})',
            person_ids,
        ).fetchall()
        result: dict[int, dict[date, str]] = {}
        for row in rows:
            result.setdefault(int(row['person_id']), {})[
                date.fromisoformat(str(row['on_date']))
            ] = str(row['company'])
        return result

    def _load_person(self, row: sqlite3.Row) -> Person:
        return _person(row, self._companies_of(int(row['id'])))

    def add_person(self, person: Person) -> int:
        with self._atomic():
            cur = self._conn.execute(
                'INSERT INTO person (display_name, pinyin, initials, role, notes, '
                'last_contact_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    person.display_name,
                    person.pinyin,
                    person.initials,
                    person.role,
                    person.notes,
                    _iso(person.last_contact_at),
                    int(person.archived),
                ),
            )
            person_id = int(cur.lastrowid or 0)
            self._replace_companies(person_id, person.companies)
            return person_id

    def update_person(self, person: Person) -> None:
        if person.id is None:
            raise ValueError('update_person 需要 person.id')
        with self._atomic():
            self._conn.execute(
                'UPDATE person SET display_name = ?, pinyin = ?, initials = ?, '
                'role = ?, notes = ?, last_contact_at = ?, archived = ? WHERE id = ?',
                (
                    person.display_name,
                    person.pinyin,
                    person.initials,
                    person.role,
                    person.notes,
                    _iso(person.last_contact_at),
                    int(person.archived),
                    person.id,
                ),
            )
            self._replace_companies(person.id, person.companies)

    def add_alias(self, person_id: int, text: str) -> None:
        # INSERT OR IGNORE + 唯一索引（I4）：重复加同一个称呼不会报错也不会写两条。
        self._conn.execute(
            'INSERT OR IGNORE INTO alias (person_id, text_norm, source) VALUES (?, ?, ?)',
            (person_id, normalize_name(text), 'user'),
        )

    def list_person_names(self) -> list[str]:
        # 所有未归档人的姓名，供离线抽取学习罕见姓氏。
        rows = self._conn.execute(
            'SELECT display_name FROM person WHERE archived = 0'
        ).fetchall()
        return [str(row['display_name']) for row in rows]


    # ---------- interaction ----------

    def add_interaction(self, interaction: Interaction) -> int:
        try:
            cur = self._conn.execute(
                'INSERT INTO interaction (person_id, capture_id, occurred_at, summary, '
                'created_at) VALUES (?, ?, ?, ?, ?)',
                (
                    interaction.person_id,
                    interaction.capture_id,
                    interaction.occurred_at.isoformat(),
                    interaction.summary,
                    interaction.created_at.isoformat(),
                ),
            )
        except sqlite3.IntegrityError as e:
            # capture_id UNIQUE（I2）：同一条 capture 只能入库一次。
            if interaction.capture_id is not None:
                raise AlreadyConfirmed(interaction.capture_id) from e
            raise
        return int(cur.lastrowid or 0)

    def list_interactions(self, person_id: int) -> list[Interaction]:
        rows = self._conn.execute(
            'SELECT * FROM interaction WHERE person_id = ? '
            'ORDER BY occurred_at DESC, id DESC',
            (person_id,),
        ).fetchall()
        return [_interaction(row) for row in rows]

    # ---------- 查询 ----------

    def list_people(self, query: str = '', limit: int = 50) -> list[Person]:
        '''最近联系优先；搜索覆盖姓名、公司历史、职位、备注和别名。'''
        base = 'SELECT DISTINCT p.* FROM person p WHERE p.archived = 0 '
        order = (
            'ORDER BY p.last_contact_at IS NULL, p.last_contact_at DESC, p.id DESC '
            'LIMIT ?'
        )
        if query:
            like = f'%{query}%'
            # 别名存的是归一化文本（去掉敬称/空白），查询也要归一化后再比。
            alias_like = f'%{normalize_name(query)}%'
            rows = self._conn.execute(
                base
                + 'AND (p.display_name LIKE ? '
                "OR IFNULL(p.role, '') LIKE ? "
                "OR IFNULL(p.notes, '') LIKE ? "
                'OR EXISTS (SELECT 1 FROM alias a WHERE a.person_id = p.id '
                'AND a.text_norm LIKE ?) '
                'OR EXISTS (SELECT 1 FROM person_company c '
                'WHERE c.person_id = p.id AND c.company LIKE ?)) '
                + order,
                (like, like, like, alias_like, like, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(base + order, (limit,)).fetchall()
        companies = self._companies_for([int(row['id']) for row in rows])
        return [
            _person(row, companies.get(int(row['id']), {})) for row in rows
        ]

    # ---------- 备份 ----------

    def export_all(self) -> dict[str, list[dict[str, object]]]:
        data: dict[str, list[dict[str, object]]] = {}
        for table in _TABLES:
            rows = self._conn.execute(f'SELECT * FROM {table}').fetchall()
            # sqlite3.Row 直接迭代得到的是「值」而不是列名，所以显式配对。
            data[table] = [dict(zip(row.keys(), row, strict=True)) for row in rows]
        return data

    def import_all(self, tables: dict[str, list[dict[str, object]]]) -> None:
        count = int(self._conn.execute('SELECT COUNT(*) FROM person').fetchone()[0])
        if count > 0:
            raise ImportTargetNotEmpty('目标库不是空库，导入已取消')
        with self.transaction():
            for table in _TABLES:
                allowed = {
                    str(r['name'])
                    for r in self._conn.execute(f'PRAGMA table_info({table})')
                }
                for raw_row in tables.get(table, []):
                    columns = list(raw_row)
                    unknown = set(columns) - allowed
                    if unknown:
                        raise BackupFormatError(f'{table} 出现未知列：{sorted(unknown)}')
                    placeholders = ', '.join('?' for _ in columns)
                    self._conn.execute(
                        f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({placeholders})',
                        tuple(raw_row[c] for c in columns),
                    )
