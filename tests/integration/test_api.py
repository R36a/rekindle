'''HTTP 层集成测试：真实 SQLite + TestClient，验证接口契约与错误码。'''

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip('fastapi')
testclient = pytest.importorskip('fastapi.testclient')

from rekindle.interfaces.api import create_app  # noqa: E402

NOW = datetime(2026, 10, 24, 9, 0)


@pytest.fixture()
def client(tmp_path: Path) -> Any:
    return testclient.TestClient(
        create_app(tmp_path / 'api.db', now_provider=lambda: NOW)
    )


def test_health(client: Any) -> None:
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'


def test_capture_confirm_and_query(client: Any) -> None:
    resp = client.post('/captures', json={'text': '昨天和张三在字节工作，他做后端'})
    assert resp.status_code == 201
    body = resp.json()
    assert body['parsed']['display_name'] == '张三'
    assert body['parsed']['company'] == '字节'

    resp = client.post(f'/captures/{body["capture_id"]}/confirm', json={})
    assert resp.status_code == 200
    confirmed = resp.json()
    assert confirmed['person_name'] == '张三'
    assert confirmed['created_new'] is True

    people = client.get('/people').json()
    assert len(people) == 1
    assert people[0]['display_name'] == '张三'
    assert people[0]['companies'] == {'2026-10-23': '字节'}

    detail = client.get(f'/people/{people[0]["id"]}').json()
    assert len(detail['interactions']) == 1
    assert '张三' in detail['interactions'][0]['summary']


def test_manual_add_merges_same_name(client: Any) -> None:
    first = client.post('/people', json={'name': '李四', 'company': '腾讯'})
    assert first.status_code == 201
    assert first.json()['created_new'] is True

    second = client.post('/people', json={'name': '李四'})
    assert second.status_code == 201
    assert second.json()['created_new'] is False
    assert second.json()['person_id'] == first.json()['person_id']


def test_confirm_twice_returns_409(client: Any) -> None:
    capture_id = client.post('/captures', json={'text': '和张三吃饭'}).json()['capture_id']
    assert client.post(f'/captures/{capture_id}/confirm', json={}).status_code == 200
    assert client.post(f'/captures/{capture_id}/confirm', json={}).status_code == 409


def test_unknown_capture_returns_404(client: Any) -> None:
    assert client.post('/captures/999/confirm', json={}).status_code == 404


def test_unknown_person_returns_404(client: Any) -> None:
    assert client.get('/people/999').status_code == 404


def test_missing_name_returns_400(client: Any) -> None:
    capture_id = client.post('/captures', json={'text': '今天见了个人'}).json()['capture_id']
    resp = client.post(f'/captures/{capture_id}/confirm', json={})
    assert resp.status_code == 400
    assert '姓名' in resp.json()['detail']


def test_list_filters_by_query(client: Any) -> None:
    client.post('/people', json={'name': '王五', 'company': '字节'})
    client.post('/people', json={'name': '赵六', 'company': '腾讯'})

    assert len(client.get('/people', params={'query': '字节'}).json()) == 1
    assert len(client.get('/people', params={'query': '腾讯'}).json()) == 1
    assert client.get('/people', params={'query': '阿里'}).json() == []


def test_validation_rejects_blank_text_and_unknown_field(client: Any) -> None:
    assert client.post('/captures', json={'text': ''}).status_code == 422
    assert client.post('/captures', json={'text': 'x', 'oops': 1}).status_code == 422
    assert client.get('/people', params={'limit': 0}).status_code == 422
