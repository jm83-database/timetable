import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from app import create_app, create_asgi_app


TENANT = '11111111-1111-4111-8111-111111111111'
AUDIENCE = 'api://timetable-mcp'


def _event(response):
    payload = next(line[6:] for line in response.text.splitlines() if line.startswith('data: '))
    return json.loads(payload)


def _token(key, roles):
    now = datetime.now(timezone.utc)
    return jwt.encode({
        'iss': f'https://login.microsoftonline.com/{TENANT}/v2.0',
        'aud': AUDIENCE,
        'sub': 'agent',
        'tid': TENANT,
        'oid': '33333333-3333-4333-8333-333333333333',
        'iat': now,
        'nbf': now,
        'exp': now + timedelta(minutes=5),
        'roles': roles,
    }, key, algorithm='RS256')


def test_streamable_http_requires_app_role_and_supports_class_reminder_setup(tmp_path, monkeypatch):
    from services import cosmos_service, reminder_storage
    from services.reminder_storage import LocalReminderStorage

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    flask_app = create_app()
    flask_app.config.update(
        TESTING=True,
        AUTH_MODE='entra',
        EMPLOYEE_TENANT_ID=TENANT,
        MCP_API_AUDIENCE=AUDIENCE,
        MCP_REQUIRED_ROLE='Timetable.ReadWrite',
        WEBSITE_SITE_NAME='timetable',
    )
    flask_app.extensions['timetable_jwks'] = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=key.public_key())
    )

    class Storage:
        def __init__(self):
            self.courses = [{
                'id': 'course-1',
                'name': 'AI 과정',
                'entries': [{
                    'id': 'entry-1',
                    'date': '2026-11-20',
                    'class_name': '기초 수업',
                    'instructor': '김강사',
                    'start_time': '09:00',
                    'end_time': '17:00',
                    'hours': 8,
                }, {
                    'id': 'entry-2',
                    'date': '2026-11-21',
                    'class_name': '기초 심화',
                    'instructor': '김강사',
                    'start_time': '09:00',
                    'end_time': '17:00',
                    'hours': 8,
                }],
            }]

        def get_all_courses(self):
            return self.courses

        def get_course_summaries(self):
            return [{
                'id': course['id'],
                'name': course['name'],
                'color': '',
                'file_name': '',
                'uploaded_at': '',
                'default_start_time': '09:00',
                'entry_count': len(course['entries']),
            } for course in self.courses]

        def add_entry(self, course_id, entry):
            if course_id != 'course-1':
                return None
            entry['id'] = 'entry-3'
            self.courses[0]['entries'].append(entry)
            return entry['id']

    storage = Storage()
    reminders = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    contact = reminders.add_contact('홍강사', 'instructor@example.com')
    reminders.add_contact('김강사', 'duplicate@example.com')
    reminders.add_contact('김강사', 'another-duplicate@example.com')
    monkeypatch.setattr(reminder_storage, 'get_reminder_storage', lambda: reminders)
    monkeypatch.setattr(cosmos_service, 'get_storage', lambda: storage)
    client_app = create_asgi_app(flask_app)
    headers = {
        'Accept': 'application/json, text/event-stream',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {_token(key, ["Timetable.ReadWrite"])}',
    }

    with TestClient(client_app) as client:
        initialized = client.post('/mcp', headers=headers, json={
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2025-03-26',
                'capabilities': {},
                'clientInfo': {'name': 'test-client', 'version': '1'},
            },
        })
        assert initialized.status_code == 200
        assert _event(initialized)['result']['serverInfo']['name'] == 'Timetable'

        tools = client.post('/mcp', headers=headers, json={
            'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {},
        })
        tool_names = {tool['name'] for tool in _event(tools)['result']['tools']}
        assert {'list_courses', 'search_classes', 'create_class', 'delete_roster_entry'} <= tool_names

        search = client.post('/mcp', headers=headers, json={
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/call',
            'params': {'name': 'search_classes', 'arguments': {'query': '기초', 'limit': 1}},
        })
        search_data = json.loads(_event(search)['result']['content'][0]['text'])
        assert search_data['returned'] == 1
        assert search_data['total_matches'] == 2
        assert search_data['truncated'] is True
        assert search_data['entries'][0]['entry_id'] == 'entry-1'

        created = client.post('/mcp', headers=headers, json={
            'jsonrpc': '2.0',
            'id': 4,
            'method': 'tools/call',
            'params': {
                'name': 'create_class',
                'arguments': {
                    'course_id': 'course-1',
                    'date': '2026-11-21',
                    'class_name': '심화 수업',
                    'instructor': '홍강사, 김강사, 미등록 강사',
                    'hours': 4,
                    'location_type': 'offline',
                    'location': '서울 교육장',
                },
            },
        })
        assert _event(created)['result']['isError'] is False
        assert storage.courses[0]['entries'][-1]['class_name'] == '심화 수업'
        created_entry = _event(created)['result']['content'][0]['text']
        created_data = json.loads(created_entry)
        assert created_data['location_type'] == 'offline'
        assert created_data['location'] == '서울 교육장'

        setup = client.post('/mcp', headers=headers, json={
            'jsonrpc': '2.0',
            'id': 7,
            'method': 'tools/call',
            'params': {
                'name': 'configure_class_reminders',
                'arguments': {
                    'course_id': 'course-1',
                    'entry_id': created_data['entry_id'],
                    'education_type': 'short_term',
                },
            },
        })
        setup_text = _event(setup)['result']['content'][0]['text']
        setup_data = json.loads(setup_text)
        assert setup_data['configured'] is True
        assert setup_data['recipient_count'] == 1
        assert setup_data['matched_instructors'] == ['홍강사']
        assert setup_data['ambiguous_instructors'] == ['김강사']
        assert setup_data['unmatched_instructors'] == ['미등록 강사']
        assert 'instructor@example.com' not in setup_text
        assignment = reminders.assignment('course-1', created_data['entry_id'])
        assert assignment['recipients'] == [contact['id']]
        assert assignment['education_type'] == 'short_term'

        denied = client.post('/mcp', headers={
            **headers,
            'Authorization': f'Bearer {_token(key, ["Timetable.Read"])}',
        }, json={
            'jsonrpc': '2.0', 'id': 5, 'method': 'tools/list', 'params': {},
        })
        assert denied.status_code == 403

        forwarded = client.post('/mcp', headers={
            key: value for key, value in headers.items() if key != 'Authorization'
        } | {'X-MS-TOKEN-AAD-ACCESS-TOKEN': _token(key, ['Timetable.ReadWrite'])}, json={
            'jsonrpc': '2.0', 'id': 6, 'method': 'tools/list', 'params': {},
        })
        assert forwarded.status_code == 200

        flask_app.config['AUTH_MODE'] = 'local'
        flask_app.config['WEBSITE_SITE_NAME'] = ''
        api_response = client.get('/api/courses')
        assert api_response.status_code == 200
        assert api_response.json()['courses'][0]['id'] == 'course-1'


def test_course_summaries_omit_entries_and_count_legacy_cosmos_documents(tmp_path, monkeypatch):
    from config import Config
    from services.cosmos_service import CosmosStorage, LocalJsonStorage

    monkeypatch.setattr(Config, 'COURSES_FILE', str(tmp_path / 'courses.json'))
    local = LocalJsonStorage()
    local.create_course({'id': 'local-course', 'name': '로컬 과정'})
    local.add_entry('local-course', {'id': 'local-entry', 'class_name': '수업'})
    local_summary = local.get_course_summaries()[0]
    assert local_summary['entry_count'] == 1
    assert 'entries' not in local_summary

    class Container:
        def __init__(self):
            self.queries = []

        def query_items(self, query, **_kwargs):
            self.queries.append(query)
            if 'GROUP BY' in query:
                return [{'course_id': 'legacy-course', 'entry_count': 3}]
            return [{
                'id': 'legacy-course',
                'name': '구형 과정',
                'color': '#4A90D9',
                'file_name': '',
                'uploaded_at': '2026-01-01',
                'default_start_time': '09:00',
            }]

    container = Container()
    summary = CosmosStorage(container).get_course_summaries()
    assert summary[0]['entry_count'] == 3
    assert len(container.queries) == 2
    assert all('SELECT *' not in query for query in container.queries)


def test_mcp_date_range_allows_at_most_366_inclusive_days():
    from services.mcp_server import _validated_date_range

    start, end = _validated_date_range('2026-01-01', '2027-01-01')
    assert (end - start).days + 1 == 366
    with pytest.raises(ValueError, match='최대 366일'):
        _validated_date_range('2026-01-01', '2027-01-02')
