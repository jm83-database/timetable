"""직원근무표 파서 테스트 — 실제 직원근무표.xlsx 시트 '10'을 픽스처로 사용"""
import os
import pytest

from services.roster_parser import parse_roster, get_roster_sheet_info, _parse_event_text, _classify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, '직원근무표.xlsx')

pytestmark = pytest.mark.skipif(not os.path.exists(XLSX), reason="직원근무표.xlsx 없음")


@pytest.fixture(scope='module')
def october():
    entries, months = parse_roster(XLSX, ['10'])
    return entries, months


def _by(entries, **kw):
    return [e for e in entries if all(e.get(k) == v for k, v in kw.items())]


def test_month_detected_from_a1_not_sheet_name():
    info = {s['name']: (s['year'], s['month']) for s in get_roster_sheet_info(XLSX)}
    assert info['10'] == (2026, 10)
    assert info['3월'] == (2027, 2)   # 시트명과 실제 월이 다름
    assert '정보' not in info


def test_october_counts(october):
    entries, months = october
    assert months == [(2026, 10)]
    office = _by(entries, category='office')
    assert len(office) == 20
    assert _by(entries, category='laptop')[0]['date'] == '2026-10-01'
    assert len(_by(entries, category='leave')) == 1


def test_office_people(october):
    entries, _ = october
    expected = {
        '2026-10-01': '황소연', '2026-10-02': '이대건', '2026-10-06': '김승준', '2026-10-07': '이대건',
        '2026-10-08': '박명균', '2026-10-12': '최진명', '2026-10-16': '박명균', '2026-10-30': '최진명',
    }
    for date, name in expected.items():
        assert _by(entries, category='office', date=date)[0]['people'] == [name]


def test_event_parsing(october):
    entries, _ = october
    e = _by(entries, category='event', date='2026-10-07', title='AI11타운홀2')[0]
    assert e['people'] == ['박명균', '황소연']

    e = _by(entries, category='event', date='2026-10-29')[0]
    assert e['title'] == 'AI11커멘'
    assert e['people'] == ['김승준', '황소연', '최진명']
    assert e['note'] == '프로젝트안내'

    # 이름만 있는 연속 행이 직전 일정에 합쳐짐
    e = _by(entries, category='event', date='2026-10-19')[0]
    assert e['title'] == '김해예정'
    assert e['people'] == ['강형주', '황소연', '최진명']


def test_leave_and_noise(october):
    entries, _ = october
    leave = _by(entries, category='leave')[0]
    assert (leave['date'], leave['people']) == ('2026-10-22', ['황소연'])
    assert not [e for e in entries if e['raw_text'].strip().lower() in ('8h', '메모')]
    assert not [e for e in entries if e['date'].startswith('2026-11')]


def test_employee_set(october):
    entries, _ = october
    people = {p for e in entries for p in e['people']}
    assert people == {'황소연', '이대건', '김승준', '박명균', '최진명', '강형주'}


@pytest.mark.parametrize('text,title,people', [
    ('숙대-최진명', '숙대', ['최진명']),
    ('이대건-마산대', '마산대', ['이대건']),
    ('AI11타운홀2_박명균, 황소연', 'AI11타운홀2', ['박명균', '황소연']),
    ('김승준-숙대 심사 (16:30~17:30)', '숙대 심사', ['김승준']),
    ('D5커리어멘토링자소서', 'D5커리어멘토링자소서', []),
])
def test_parse_event_text(text, title, people):
    t, p, _ = _parse_event_text(text, {'최진명', '이대건', '박명균', '황소연', '김승준'})
    assert (t, p) == (title, people)


def test_classify_leave_variants():
    assert _classify('황소연 휴가', set())[:3] == ('leave', '휴가', ['황소연'])
    assert _classify('최진명-휴가', set())[:3] == ('leave', '휴가', ['최진명'])
    assert _classify('대체휴일', set())[0] == 'memo'


def test_all_sheets_parse_without_error():
    names = [s['name'] for s in get_roster_sheet_info(XLSX)]
    entries, months = parse_roster(XLSX, names)
    assert len(months) == len(names)
    assert all(e['category'] in ('office', 'laptop', 'event', 'leave', 'memo') for e in entries)
