'''HTTP 接口层：把 app/ 的用例暴露成 REST API。

设计约束（与 CLI / GUI 一致）：
- 只做参数解析、错误映射与序列化，业务逻辑全在 app/；
- 每个请求独立开一个 SQLite 连接，避免多线程共享同一个连接；
- 「现在几点」由 app.state.now_provider 提供，测试可注入固定时间。

启动：rekindle-api --db ~/.rekindle/rekindle.db
'''

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from rekindle import __version__
from rekindle.app import queries, record
from rekindle.app.queries import PersonDetail
from rekindle.app.record import ConfirmResult, RecordedCapture
from rekindle.domain.errors import (
    AlreadyConfirmed,
    CaptureNotFound,
    PersonNotFound,
    RekindleError,
    RelationExists,
)
from rekindle.domain.limits import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    RAW_TEXT_MAX_LENGTH,
)
from rekindle.domain.models import ExtractedFields, Person
from rekindle.domain.text import NAME_MAX_LENGTH
from rekindle.infra.sqlite_repo import SqliteRepo
from rekindle.interfaces.config import default_db_path


class _Body(BaseModel):
    '''请求体：拒绝未知字段，避免拼错字段被静默忽略。'''

    model_config = ConfigDict(extra='forbid')


class CaptureIn(_Body):
    text: str = Field(min_length=1, max_length=RAW_TEXT_MAX_LENGTH)


class ConfirmIn(_Body):
    name: str | None = None
    company: str | None = None
    role: str | None = None
    fields: dict[str, list[str]] | None = None
    occurred_on: date | None = None
    create_new: bool = False


class ManualIn(_Body):
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    company: str | None = None
    role: str | None = None
    fields: dict[str, list[str]] | None = None
    occurred_on: date | None = None


class _Out(BaseModel):
    '''出参：直接从领域对象读属性（from_attributes），不再逐字段搬运。

    以前是「PersonOut + _person_out()」这样一对一复制字段的写法：领域模型加一个字段，
    这里要记得同步，否则接口少一个字段且没人发现。现在是投影 + 一个序列化器。
    '''

    model_config = ConfigDict(from_attributes=True)


class PersonOut(_Out):
    id: int
    display_name: str
    role: str | None = None
    companies: dict[date, str]
    fields: dict[str, list[str]]
    last_contact_at: datetime | None = None
    archived: bool

    @field_serializer('companies')
    def _companies_as_iso(self, value: dict[date, str]) -> dict[str, str]:
        '''JSON 对象的键只能是字符串：日期 → ISO。'''
        return {day.isoformat(): company for day, company in value.items()}


class InteractionOut(_Out):
    id: int
    occurred_at: datetime
    summary: str


class PersonDetailOut(_Out):
    person: PersonOut
    interactions: list[InteractionOut]


class ConfirmOut(_Out):
    person_id: int
    person_name: str
    created_new: bool
    interaction_id: int


class CaptureOut(_Out):
    capture_id: int
    parsed: ExtractedFields


def _status_for(exc: RekindleError) -> int:
    '''业务错误 → HTTP 状态码：找不到 404，重复 409，其余 400。'''
    if isinstance(exc, (CaptureNotFound, PersonNotFound)):
        return 404
    if isinstance(exc, (AlreadyConfirmed, RelationExists)):
        return 409
    return 400


def get_repo(request: Request) -> Iterator[SqliteRepo]:
    '''每个请求一个连接：SQLite 连接不跨线程共享。'''
    repo = SqliteRepo(request.app.state.db_path)
    try:
        yield repo
    finally:
        repo.close()


def get_now(request: Request) -> datetime:
    provider: Callable[[], datetime] = request.app.state.now_provider
    return provider()


RepoDep = Annotated[SqliteRepo, Depends(get_repo)]
NowDep = Annotated[datetime, Depends(get_now)]


def create_app(
    db_path: str | Path,
    *,
    now_provider: Callable[[], datetime] = datetime.now,
) -> FastAPI:
    '''构造应用；测试用 now_provider 注入固定时间。'''
    app = FastAPI(title='rekindle API', version=__version__)
    path = Path(db_path)
    app.state.db_path = path
    app.state.now_provider = now_provider

    # 启动时建表：避免多个请求同时初始化 schema。
    # 注意必须用文件路径，:memory: 每个连接是独立的空库。
    SqliteRepo(path).close()

    @app.exception_handler(RekindleError)
    async def _on_rekindle_error(_: Request, exc: RekindleError) -> JSONResponse:
        return JSONResponse(status_code=_status_for(exc), content={'detail': str(exc)})

    @app.get('/health')
    def health() -> dict[str, str]:
        return {'status': 'ok', 'version': __version__}

    @app.post('/captures', status_code=201, response_model=CaptureOut)
    def create_capture(
        body: CaptureIn, repo: RepoDep, now: NowDep
    ) -> RecordedCapture:
        return record.record(repo, body.text, now)

    @app.post('/captures/{capture_id}/confirm', response_model=ConfirmOut)
    def confirm_capture(
        capture_id: int, body: ConfirmIn, repo: RepoDep, now: NowDep
    ) -> ConfirmResult:
        return record.confirm(
            repo,
            capture_id,
            now=now,
            display_name=body.name,
            company=body.company,
            role=body.role,
            fields=body.fields,
            occurred_on=body.occurred_on,
            create_new=body.create_new,
        )

    @app.post('/people', status_code=201, response_model=ConfirmOut)
    def create_person(body: ManualIn, repo: RepoDep, now: NowDep) -> ConfirmResult:
        return record.manual(
            repo,
            now=now,
            display_name=body.name,
            company=body.company,
            role=body.role,
            fields=body.fields,
            occurred_on=body.occurred_on,
        )

    @app.get('/people', response_model=list[PersonOut])
    def list_people(
        repo: RepoDep,
        query: str = '',
        limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
    ) -> list[Person]:
        return queries.list_people(repo, query, limit)

    @app.get('/people/{person_id}', response_model=PersonDetailOut)
    def person_detail(person_id: int, repo: RepoDep) -> PersonDetail:
        return queries.person_detail(repo, person_id)

    return app


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='rekindle-api', description='rekindle HTTP API')
    parser.add_argument('--db', default=str(default_db_path()))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(create_app(Path(args.db)), host=args.host, port=args.port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
