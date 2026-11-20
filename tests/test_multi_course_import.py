from datetime import datetime, time
from io import BytesIO

import openpyxl

from app import create_app
from config import Config
import services.cosmos_service as cosmos_service
from services.excel_parser import (
    MULTI_COURSE_HEADERS,
    create_multi_course_template,
    detect_timetable_format,
    parse_multi_course_timetable,
)


def _write_multi_course_workbook(path, rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = '수업목록'
    sheet.append(MULTI_COURSE_HEADERS)
    for row in rows:
        sheet.append(row)
    workbook.create_sheet('작성안내')
    workbook.save(path)


def _sample_rows():
    return [
        [datetime(2026, 11, 20), 'AI 과정 A', 'AI 기초', '홍길동',
         time(9), time(12), '온라인', '', 'https://padlet.com/a', 'https://zoom.us/a'],
        [datetime(2026, 11, 20), '데이터 과정 B', '데이터 분석', '김강사',
         time(9), time(18), '오프라인', '서울 교육장', '', ''],
        [datetime(2026, 11, 21), 'AI 과정 A', 'AI 실습', '홍길동',
         time(13), time(17), '온라인', '', '', 'https://teams.microsoft.com/a'],
    ]


def test_template_download_contains_multi_course_columns_and_instructions():
    workbook = openpyxl.load_workbook(create_multi_course_template(), data_only=True)
    assert workbook.sheetnames == ['수업목록', '작성안내']
    assert tuple(cell.value for cell in workbook['수업목록'][1]) == MULTI_COURSE_HEADERS
    assert '한 행에 수업 하나' in workbook['작성안내']['A2'].value
    assert len(workbook['수업목록'].data_validations.dataValidation) == 1


def test_table_parser_accepts_multiple_courses_and_same_day_classes(tmp_path):
    path = tmp_path / 'multi.xlsx'
    _write_multi_course_workbook(path, _sample_rows())

    assert detect_timetable_format(path) == 'multi_course'
    entries = parse_multi_course_timetable(path)

    assert len(entries) == 3
    assert [entry['course_name'] for entry in entries] == [
        'AI 과정 A', '데이터 과정 B', 'AI 과정 A',
    ]
    assert entries[0]['date'] == entries[1]['date'] == '2026-11-20'
    assert entries[0]['hours'] == 3
    assert entries[1]['hours'] == 8
    assert entries[0]['online_class_url'] == 'https://zoom.us/a'
    assert entries[1]['location'] == '서울 교육장'


def test_upload_api_groups_entries_by_course_and_validates_before_saving(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(tmp_path))
    path = tmp_path / 'multi.xlsx'
    _write_multi_course_workbook(path, _sample_rows())

    class Storage:
        def __init__(self):
            self.saved = []

        def save_course(self, course, entries):
            self.saved.append((course, entries))

    storage = Storage()
    monkeypatch.setattr(cosmos_service, 'get_storage', lambda: storage)
    app = create_app()
    app.config.update(TESTING=True, AUTH_MODE='local', WEBSITE_SITE_NAME='')
    client = app.test_client()

    response = client.post('/api/upload', json={
        'filepath': str(path), 'sheets': [], 'format': 'multi_course',
    })
    assert response.status_code == 200
    assert response.json['course_count'] == 2
    assert response.json['entry_count'] == 3
    assert [course['name'] for course, _ in storage.saved] == ['AI 과정 A', '데이터 과정 B']
    assert len(storage.saved[0][1]) == 2
    assert storage.saved[0][1][0]['online_class_url'] == 'https://zoom.us/a'
    assert not path.exists()

    invalid_path = tmp_path / 'invalid.xlsx'
    invalid_rows = _sample_rows()
    invalid_rows[1][8] = 'javascript:alert(1)'
    _write_multi_course_workbook(invalid_path, invalid_rows)
    invalid = client.post('/api/upload', json={'filepath': str(invalid_path), 'sheets': []})
    assert invalid.status_code == 400
    assert '3행' in invalid.json['error']
    assert len(storage.saved) == 2


def test_sheets_api_recognizes_template_without_sheet_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(tmp_path))
    template = create_multi_course_template()
    app = create_app()
    app.config.update(TESTING=True, AUTH_MODE='local', WEBSITE_SITE_NAME='')
    client = app.test_client()

    upload_page = client.get('/upload')
    assert upload_page.status_code == 200
    assert 'href="/api/templates/multi-course.xlsx"' in upload_page.get_data(as_text=True)
    download = client.get('/api/templates/multi-course.xlsx')
    assert download.status_code == 200
    assert download.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    response = client.post('/api/sheets', data={
        'file': (BytesIO(template.getvalue()), 'multi-course.xlsx'),
    }, content_type='multipart/form-data')

    assert response.status_code == 200
    assert response.json['format'] == 'multi_course'
    assert response.json['sheets'] == []


def test_legacy_calendar_workbook_is_not_mistaken_for_table(tmp_path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.cell(row=10, column=3, value=datetime(2026, 11, 20))
    sheet.cell(row=10, column=4, value='기존 수업')
    path = tmp_path / 'legacy.xlsx'
    workbook.save(path)

    assert detect_timetable_format(path) == 'vertex42'
