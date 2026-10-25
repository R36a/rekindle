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
from pydantic import BaseModel, ConfigDict, Field

from rekindle import __version__
from rekindle.app import queries, record
from rekindle.app.record import ConfirmResult
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
from rekindle.domain.models import ExtractedFields, Interaction, Person
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


class PersonOut(BaseModel):
    '''对外的人：日期键转成 ISO 字符串，避免 JSON 对象键类型问题。'''

    id: int
    display_name: str
    role: str | None = None
    companies: dict[str, str]
    fields: dict[str, list[str]]
    last_contact_at: datetime | None = None
    archived: bool


class InteractionOut(BaseModel):
    id: int
    occurred_at: datetime
    summary: str


class PersonDetailOut(BaseModel):
    person: PersonOut
    interactions: list[InteractionOut]


class ConfirmOut(BaseModel):
    person_id: int
    person_name: str
    created_new: bool
    interaction_id: int


class CaptureOut(BaseModel):
    capture_id: int
    parsed: ExtractedFields


def _person_out(person: Person) -> PersonOut:
    return PersonOut(
        id=person.id or 0,
        display_name=person.display_name,
        role=person.role,
        companies={
            day.isoformat(): company for day, company in person.companies.items()
        },
        fields=person.fields,
        last_contact_at=person.last_contact_at,
        archived=person.archived,
    )


def _interaction_out(item: Interaction) -> InteractionOut:
    return InteractionOut(
        id=item.id or 0,
        occurred_at=item.occurred_at,
        summary=item.summary,
    )


def _confirm_out(result: ConfirmResult) -> ConfirmOut:
    return ConfirmOut(
        person_id=result.person_id,
        person_name=result.person_name,
        created_new=result.created_new,
        interaction_id=result.interaction_id,
    )


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
    def create_capture(body: CaptureIn, repo: RepoDep, now: NowDep) -> CaptureOut:
        result = record.record(repo, body.text, now)
        return CaptureOut(capture_id=result.capture_id, parsed=result.parsed)

    @app.post('/captures/{capture_id}/confirm', response_model=ConfirmOut)
    def confirm_capture(
        capture_id: int, body: ConfirmIn, repo: RepoDep, now: NowDep
    ) -> ConfirmOut:
        return _confirm_out(
            record.confirm(
                repo,
                capture_id,
                now=now,
                name=body.name,
                company=body.company,
                role=body.role,
                fields=body.fields,
                occurred_on=body.occurred_on,
                create_new=body.create_new,
            )
        )

    @app.post('/people', status_code=201, response_model=ConfirmOut)
    def create_person(body: ManualIn, repo: RepoDep, now: NowDep) -> ConfirmOut:
        return _confirm_out(
            record.manual(
                repo,
                now=now,
                name=body.name,
                company=body.company,
                role=body.role,
                fields=body.fields,
                occurred_on=body.occurred_on,
            )
        )

    @app.get('/people', response_model=list[PersonOut])
    def list_people(
        repo: RepoDep,
        query: str = '',
        limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
    ) -> list[PersonOut]:
        return [_person_out(person) for person in queries.list_people(repo, query, limit)]

    @app.get('/people/{person_id}', response_model=PersonDetailOut)
    def person_detail(person_id: int, repo: RepoDep) -> PersonDetailOut:
        detail = queries.person_detail(repo, person_id)
        return PersonDetailOut(
            person=_person_out(detail.person),
            interactions=[_interaction_out(item) for item in detail.interactions],
        )

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
