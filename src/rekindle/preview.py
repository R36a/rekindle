'''命令行预览：用规则抽取一句话，把结果打印出来。

用法：
    python -m rekindle.preview "上周和张三在字节工作，他做后端，答应帮我下周看简历"
'''

from __future__ import annotations

import argparse
import sys
from datetime import date

from rekindle.domain.extract_rule import extract
from rekindle.domain.models import ExtractedFields


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='rekindle.preview',
        description='规则抽取预览（离线，零网络）',
    )
    parser.add_argument('text', help='一句话，用引号包起来')
    return parser


def _show(result: ExtractedFields) -> None:
    print('姓名   :', result.display_name)
    print('公司   :', result.company)
    print('职位   :', result.role)
    print('时间   :', result.occurred_at)
    print('联系间隔:', result.cadence_days)
    if result.todos:
        for todo in result.todos:
            print('待办   :', todo.title)
            print('  到期:', todo.due_on)
            print('  涉及:', todo.people_names)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = extract(args.text, date.today())
    _show(result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
