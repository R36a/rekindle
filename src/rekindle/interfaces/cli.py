'''命令行外壳：只做参数解析、装配与打印，业务全在 app/。

命令：
    remember "一句话"        → 规则抽取，存草稿（不入库）
    confirm <capture_id>    → 用户确认后写 person / interaction
    list / show / alias / discard / export / import
'''

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from rekindle import __version__
from rekindle.app import backup, queries, record
from rekindle.app.queries import PersonDetail
from rekindle.domain.errors import RekindleError
from rekindle.domain.models import ExtractedFields, Person
from rekindle.infra.sqlite_repo import SqliteRepo
from rekindle.interfaces.config import default_db_path


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('日期格式应为 YYYY-MM-DD') from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='rekindle',
        description='本地优先的个人人脉管理器（离线原型：只做规则抽取）',
    )
    parser.add_argument('--version', action='version', version=f'rekindle {__version__}')

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        '--db',
        default=str(default_db_path()),
        help='数据库文件（默认 ~/.rekindle/rekindle.db，可用 REKINDLE_DB 覆盖）',
    )
    sub = parser.add_subparsers(dest='command', metavar='命令')

    p = sub.add_parser('remember', parents=[common], help='记一句话（只存草稿）')
    p.add_argument('text', help='一句话原文，用引号包起来')

    p = sub.add_parser('confirm', parents=[common], help='确认草稿并入库')
    p.add_argument('capture_id', type=int)
    p.add_argument('--name', help='姓名（抽不到时必填）')
    p.add_argument('--company')
    p.add_argument('--role')
    p.add_argument('--when', type=_parse_date, dest='occurred_on', help='联系日期 YYYY-MM-DD')
    p.add_argument('--new', action='store_true', dest='create_new', help='即使同名也新建')

    p = sub.add_parser('list', parents=[common], help='列出联系人（最近联系优先）')
    p.add_argument('-q', '--query', default='', help='按姓名/公司/职位/备注/别名搜索')
    p.add_argument('-n', '--limit', type=int, default=20)

    p = sub.add_parser('show', parents=[common], help='查看一个人')
    p.add_argument('person_id', type=int)

    p = sub.add_parser('alias', parents=[common], help='给某个人记一个称呼')
    p.add_argument('person_id', type=int)
    p.add_argument('text')

    p = sub.add_parser('discard', parents=[common], help='丢弃草稿')
    p.add_argument('capture_id', type=int)

    p = sub.add_parser('export', parents=[common], help='导出 JSON 备份')
    p.add_argument('path')

    p = sub.add_parser('import', parents=[common], help='从 JSON 备份导入（仅空库）')
    p.add_argument('path')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    now = datetime.now()
    try:
        with SqliteRepo(Path(args.db)) as repo:
            return _run(args, repo, now)
    except RekindleError as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 1


def _run(args: argparse.Namespace, repo: SqliteRepo, now: datetime) -> int:
    if args.command == 'remember':
        saved = record.record(repo, args.text, now)
        print(f'已保存草稿 capture #{saved.capture_id}（规则抽取，离线）')
        _print_fields(saved.parsed)
        print(f'\n确认入库：rekindle confirm {saved.capture_id}')
        return 0

    if args.command == 'confirm':
        result = record.confirm(
            repo,
            args.capture_id,
            now=now,
            name=args.name,
            company=args.company,
            role=args.role,
            occurred_on=args.occurred_on,
            create_new=args.create_new,
        )
        action = '新建' if result.created_new else '合并到已有'
        print(f'已确认 → {result.person_name}（{action}，#{result.person_id}）')
        return 0

    if args.command == 'list':
        people = queries.list_people(repo, args.query, args.limit)
        if not people:
            print('没有匹配的联系人。先用 rekindle remember "一句话" 记一个。')
            return 0
        for person in people:
            _print_person_line(person)
        return 0

    if args.command == 'show':
        _print_detail(queries.person_detail(repo, args.person_id))
        return 0

    if args.command == 'alias':
        repo.add_alias(args.person_id, args.text)
        print(f'已记住称呼：{args.text} → #{args.person_id}')
        return 0

    if args.command == 'discard':
        repo.discard_capture(args.capture_id)
        print(f'已丢弃 capture #{args.capture_id}')
        return 0

    if args.command == 'export':
        path = backup.export_to(repo, args.path, now)
        print(f'已导出 → {path.resolve()}')
        return 0

    if args.command == 'import':
        count = backup.import_from(repo, args.path)
        print(f'已导入 {count} 位联系人')
        return 0

    print(f'未知命令：{args.command}', file=sys.stderr)
    return 2


def _print_fields(parsed: ExtractedFields) -> None:
    print('姓名    :', parsed.display_name or '（未识别，确认时用 --name 指定）')
    print('公司    :', parsed.company or '-')
    print('职位    :', parsed.role or '-')
    print('时间    :', parsed.occurred_at or '（未识别，默认今天）')


def _print_person_line(person: Person) -> None:
    parts = [f'#{person.id or 0:<3}', person.display_name]
    extra = ' / '.join(item for item in (person.company, person.role) if item)
    if extra:
        parts.append(extra)
    if person.last_contact_at is not None:
        parts.append(f'最近 {person.last_contact_at.date()}')
    print('  '.join(parts))


def _print_detail(detail: PersonDetail) -> None:
    person = detail.person
    extra = ' / '.join(item for item in (person.company, person.role) if item)
    title = f'#{person.id} {person.display_name}'
    print(f'{title}（{extra}）' if extra else title)
    print(
        f'最近联系：{person.last_contact_at.date()}'
        if person.last_contact_at
        else '最近联系：-'
    )

    print('\n交往记录：')
    if not detail.interactions:
        print('  （无）')
    for item in detail.interactions:
        print(f'  {item.occurred_at.date()}  {item.summary}')
