"""수업 장소 및 접속 링크 파싱, 검증, 표시, 메일 테스트"""
from datetime import datetime

import openpyxl
import pytest

from app import create_app
from config import Config
from routes import _resolve_class_links, _resolve_location
import services.cosmos_service as cosmos_service
from services.calendar_service import format_events
from services.cosmos_service import CosmosStorage, LocalJsonStorage
from services.excel_parser import _location_fields, _split_location, parse_timetable
from services.reminder_sender import message_for


def _write_timetable(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '1기'
    ws.cell(row=10, column=3, value=datetime(2026, 11, 4))
    ws.cell(row=10, column=4, value='AI기본 ?서울특별시교육청 OO로 1')
    ws.cell(row=11, column=4, value='강명호')
    ws.cell(row=10, column=5, value=datetime(2026, 11, 5))
    ws.cell(row=10, column=6, value='AI심화')
    ws.cell(row=11, column=6, value='인선미')
    ws.cell(row=12, column=6, value='?온라인')
    wb.save(path)


def test_split_location_handles_halfwidth_and_fullwidth_marks():
    assert _split_location('AI기본 ?서울 OO로') == ('AI기본', '서울 OO로')
    assert _split_location('AI기본 ？온라인') == ('AI기본', '온라인')
    assert _split_location('강명호') == ('강명호', None)


def test_location_fields_defaults_to_online():
    assert _location_fields(None) == {'location_type': 'online', 'location': ''}
    assert _location_fields('온라인') == {'location_type': 'online', 'location': ''}
    assert _location_fields('서울특별시교육청') == {'location_type': 'offline', 'location': '서울특별시교육청'}


def test_parse_timetable_extracts_location_per_entry(tmp_path):
    path = tmp_path / 'timetable.xlsx'
    _write_timetable(path)

    entries = {e['class_name']: e for e in parse_timetable(str(path), ['1기'])}

    offline = entries['AI기본']
    assert offline['instructor'] == '강명호'
    assert offline['location_type'] == 'offline'
    assert offline['location'] == '서울특별시교육청 OO로 1'

    online = entries['AI심화']
    assert online['instructor'] == '인선미'
    assert online['location_type'] == 'online'
    assert online['location'] == ''


def test_resolve_location_validates_offline_input():
    assert _resolve_location({'location_type': 'online', 'location': '무시'}) == {
        'location_type': 'online', 'location': ''}
    assert _resolve_location({'location_type': 'offline', 'location': ' 서울교육청 '}) == {
        'location_type': 'offline', 'location': '서울교육청'}
    with pytest.raises(ValueError):
        _resolve_location({'location_type': 'offline', 'location': '   '})
    with pytest.raises(ValueError):
        _resolve_location({'location_type': 'offline', 'location': 'a' * 201})
    with pytest.raises(ValueError):
        _resolve_location({'location_type': 'hybrid'})


def test_class_links_are_optional_http_urls_and_online_only():
    assert _resolve_class_links({
        'course_material_url': ' https://padlet.com/class ',
        'online_class_url': 'https://teams.microsoft.com/meeting',
    }, 'online') == {
        'course_material_url': 'https://padlet.com/class',
        'online_class_url': 'https://teams.microsoft.com/meeting',
    }
    assert _resolve_class_links({
        'course_material_url': '',
        'online_class_url': 'javascript:alert(1)',
    }, 'offline') == {'course_material_url': '', 'online_class_url': ''}

    for invalid_url in ('javascript:alert(1)', '//example.com', 'https://', 'https://exa mple.com'):
        with pytest.raises(ValueError):
            _resolve_class_links({'course_material_url': invalid_url}, 'online')
    with pytest.raises(ValueError):
        _resolve_class_links({'online_class_url': 123}, 'online')


def test_entry_api_validates_and_saves_class_links(monkeypatch):
    class Storage:
        def add_entry(self, course_id, entry):
            self.entry = entry
            return 'lesson'

        def update_entry(self, course_id, entry_id, updates):
            self.updates = updates
            return True

    storage = Storage()
    monkeypatch.setattr(cosmos_service, 'get_storage', lambda: storage)
    app = create_app()
    app.config.update(TESTING=True, AUTH_MODE='local', WEBSITE_SITE_NAME='')
    client = app.test_client()
    payload = {
        'date': '2026-11-04', 'class_name': '수업',
        'start_time': '09:00', 'end_time': '18:00',
        'course_material_url': 'https://padlet.com/class',
        'online_class_url': 'https://zoom.us/j/123',
    }

    response = client.post('/api/courses/course/entries', json=payload)
    assert response.status_code == 200
    assert storage.entry['course_material_url'] == payload['course_material_url']
    assert storage.entry['online_class_url'] == payload['online_class_url']

    dashboard = client.get('/dashboard').get_data(as_text=True)
    assert 'id="add-course-material-url"' in dashboard
    assert 'id="add-online-class-url"' in dashboard
    assert 'id="edit-course-material-url"' in dashboard
    assert 'id="edit-online-class-url"' in dashboard

    invalid = client.post('/api/courses/course/entries', json={
        **payload, 'course_material_url': 'javascript:alert(1)',
    })
    assert invalid.status_code == 400

    offline = client.put('/api/courses/course/entries/lesson', json={
        **payload, 'location_type': 'offline', 'location': '교육장',
    })
    assert offline.status_code == 200
    assert storage.updates['course_material_url'] == payload['course_material_url']
    assert storage.updates['online_class_url'] == ''


def test_local_and_cosmos_storage_update_class_links(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'COURSES_FILE', str(tmp_path / 'courses.json'))
    local = LocalJsonStorage()
    local.create_course({'id': 'course', 'name': '교육'})
    local.add_entry('course', {'id': 'lesson', 'class_name': '수업'})
    updates = {
        'course_material_url': 'https://padlet.com/class',
        'online_class_url': 'https://zoom.us/j/123',
    }
    assert local.update_entry('course', 'lesson', updates)
    local_entry = local.get_all_courses()[0]['entries'][0]
    assert local_entry['course_material_url'] == updates['course_material_url']
    assert local_entry['online_class_url'] == updates['online_class_url']

    class Container:
        entry = {'id': 'lesson', 'type': 'entry', 'course_id': 'course'}

        def query_items(self, **kwargs):
            return [self.entry]

        def replace_item(self, item, body):
            self.entry = body

    container = Container()
    assert CosmosStorage(container).update_entry('course', 'lesson', updates)
    assert container.entry['course_material_url'] == updates['course_material_url']
    assert container.entry['online_class_url'] == updates['online_class_url']


def test_calendar_events_include_class_links():
    event = format_events([{
        'id': 'course', 'name': '교육', 'entries': [{
            'id': 'lesson', 'date': '2026-11-04', 'class_name': '수업',
            'course_material_url': 'https://padlet.com/class',
            'online_class_url': 'https://zoom.us/j/123',
        }],
    }])[0]
    assert event['extendedProps']['course_material_url'] == 'https://padlet.com/class'
    assert event['extendedProps']['online_class_url'] == 'https://zoom.us/j/123'


def test_mail_body_includes_online_or_offline_location():
    course = {'name': '교육'}
    base = {'class_name': '수업', 'date': '2026-11-04', 'start_time': '09:00',
            'end_time': '18:00', 'instructor': '강사'}

    _, online_body = message_for(course, {**base, 'location_type': 'online', 'location': ''}, 7)
    assert '장소: 온라인' in online_body
    with_links = {
        **base,
        'location_type': 'online',
        'course_material_url': 'https://padlet.com/class',
        'online_class_url': 'https://zoom.us/j/123',
    }
    _, online_link_body = message_for(course, with_links, 7)
    assert '강의자료 링크: https://padlet.com/class' in online_link_body
    assert '온라인 수업 링크: https://zoom.us/j/123' in online_link_body

    _, offline_body = message_for(course, {
        **with_links, 'location_type': 'offline', 'location': '서울특별시교육청',
    }, 3)
    assert '장소: 서울특별시교육청' in offline_body
    assert '강의자료 링크: https://padlet.com/class' in offline_body
    assert '온라인 수업 링크:' not in offline_body

    _, legacy_body = message_for(course, base, 7)
    assert '장소: 온라인' in legacy_body
