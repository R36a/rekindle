'''只读用例：列表、详情。

「现在几点」由调用方传入，便于测试时用假时间。
'''

from __future__ import annotations

from dataclasses import dataclass

from rekindle.app.ports import QueryPort
from rekindle.domain.errors import PersonNotFound
from rekindle.domain.models import Interaction, Person


@dataclass(frozen=True)
class PersonDetail:
    person: Person
    interactions: list[Interaction]


def list_people(repo: QueryPort, query: str = '', limit: int = 50) -> list[Person]:
    return repo.list_people(query, limit)


def person_detail(repo: QueryPort, person_id: int) -> PersonDetail:
    person = repo.get_person(person_id)
    if person is None:
        raise PersonNotFound(person_id)
    return PersonDetail(
        person=person,
        interactions=repo.list_interactions(person_id),
    )
