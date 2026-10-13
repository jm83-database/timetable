"""수업시간 계산 (분 단위 소수 허용) 테스트"""
import pytest

from services.excel_parser import calculate_end_time, calculate_hours, normalize_hours


@pytest.mark.parametrize("start, hours, expected", [
    ("09:00", 8, "18:00"),       # 점심시간 포함
    ("09:00", 4, "13:00"),       # 13:00 정각 종료 → 점심 미포함
    ("09:00", 4.5, "14:30"),     # 13:00을 넘기면 점심 1시간 추가
    ("13:00", 4.5, "17:30"),     # 오후 시작은 점심 미포함
    ("13:30", 4, "17:30"),
    ("14:00", 2.25, "16:15"),
    ("09:00", 3 + 20 / 60, "12:20"),
])
def test_calculate_end_time(start, hours, expected):
    assert calculate_end_time(start, hours) == expected


@pytest.mark.parametrize("start, end, expected", [
    ("09:00", "18:00", 8),
    ("13:00", "17:30", 4.5),
    ("09:00", "14:30", 4.5),
    ("09:00", "13:30", 4),       # 점심시간과 겹치는 30분 제외
    ("12:30", "13:30", 0.5),
    ("09:00", "12:20", 3 + 20 / 60),
    ("10:00", "10:00", None),
    ("10:00", "09:00", None),
])
def test_calculate_hours(start, end, expected):
    assert calculate_hours(start, end) == expected


def test_round_trip_matches_server_rule():
    for start in ("09:00", "09:30", "13:00", "14:00"):
        for hours in (0.5, 1, 2.25, 4, 4.5, 8):
            assert calculate_hours(start, calculate_end_time(start, hours)) == hours


@pytest.mark.parametrize("value, expected", [
    (8, 8), (8.0, 8), (4.5, 4.5), ("4.5", 4.5),
    (4.333, 4.333333333333333),  # 분 단위 반올림
    (True, None), ("abc", None), (None, None), (float('inf'), None),
])
def test_normalize_hours(value, expected):
    assert normalize_hours(value) == expected
