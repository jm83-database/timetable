"""
FullCalendar 이벤트 포맷 변환 서비스
"""
from collections import defaultdict

from config import Config

ROSTER_CATEGORY_LABELS = {
    'office': '사무실',
    'laptop': '노트북',
    'event': '일정',
    'leave': '휴가',
    'memo': '메모',
}
# 월 뷰에서 같은 날 항목 정렬 순서
ROSTER_CATEGORY_ORDER = {'office': 0, 'leave': 1, 'event': 2, 'laptop': 3, 'memo': 4}


def build_employee_colors(entries):
    """등장 빈도순으로 직원마다 팔레트 색 할당"""
    counts = defaultdict(int)
    for e in entries:
        for p in e.get('people', []):
            counts[p] += 1
    ordered = sorted(counts, key=lambda n: (-counts[n], n))
    palette = Config.COURSE_COLORS
    return {name: palette[i % len(palette)] for i, name in enumerate(ordered)}


def _roster_title(entry):
    cat = entry.get('category', 'event')
    people = ', '.join(entry.get('people', []))
    title = entry.get('title', '')
    if cat == 'office':
        return f"🏢 {people}" if people else f"🏢 {entry.get('note') or '사무실근무'}"
    if cat == 'leave':
        return f"🌴 {people} {title}".strip()
    if cat == 'laptop':
        return f"💻 {entry.get('note') or title}"
    if people and title:
        return f"{title} · {people}"
    return people or title or entry.get('note', '')


def format_roster_events(entries, employee_colors=None):
    """근무표 항목 → FullCalendar 종일 이벤트"""
    employee_colors = employee_colors or build_employee_colors(entries)
    events = []
    for e in sorted(entries, key=lambda x: (x.get('date', ''), ROSTER_CATEGORY_ORDER.get(x.get('category'), 9))):
        cat = e.get('category', 'event')
        people = e.get('people', [])
        if len(people) == 1 and cat != 'leave':
            color = employee_colors.get(people[0], Config.ROSTER_CATEGORY_COLORS.get(cat))
        else:
            color = Config.ROSTER_CATEGORY_COLORS.get(cat, '#6B7280')
        events.append({
            "id": e.get('id', ''),
            "title": _roster_title(e),
            "start": e.get('date', ''),
            "allDay": True,
            "color": color,
            "textColor": "#ffffff",
            "extendedProps": {
                "entry_id": e.get('id', ''),
                "category": cat,
                "category_label": ROSTER_CATEGORY_LABELS.get(cat, cat),
                "title": e.get('title', ''),
                "people": people,
                "note": e.get('note', ''),
                "raw_text": e.get('raw_text', ''),
                "source_sheet": e.get('source_sheet', ''),
            },
        })
    return events


def get_roster_day_summary(entries, date):
    """특정 날짜의 근무자/휴무자/일정 요약"""
    day = [e for e in entries if e.get('date') == date]
    grouped = {'office': [], 'leave': [], 'event': [], 'laptop': [], 'memo': []}
    for e in day:
        grouped.setdefault(e.get('category', 'event'), []).append(e)
    office_people = [p for e in grouped['office'] for p in e.get('people', [])]
    leave_people = [p for e in grouped['leave'] for p in e.get('people', [])]
    out_people = sorted({p for e in grouped['event'] for p in e.get('people', [])})
    return {
        "date": date,
        "office": office_people,
        "leave": leave_people,
        "out": [p for p in out_people if p not in office_people and p not in leave_people],
        "events": grouped['event'],
        "laptop": grouped['laptop'],
        "memo": grouped['memo'],
    }


def format_events(courses, course_id_filter=None):
    """과정 데이터를 FullCalendar 이벤트 JSON 포맷으로 변환"""
    events = []

    for course in courses:
        if course_id_filter and course.get('id') != course_id_filter:
            continue

        color = course.get('color', '#4A90D9')
        course_name = course.get('name', '')
        cid = course.get('id', '')

        for entry in course.get('entries', []):
            date = entry.get('date', '')
            is_holiday = entry.get('is_holiday', False)

            entry_id = entry.get('id', '')

            if is_holiday:
                # 공휴일은 종일 이벤트로 표시
                event = {
                    "id": entry_id or f"{cid}_holiday_{date}",
                    "title": f"[휴일] {entry.get('class_name', '')}",
                    "start": date,
                    "allDay": True,
                    "color": "#f3f4f6",
                    "textColor": "#ef4444",
                    "borderColor": "#fecaca",
                    "display": "block",
                    "extendedProps": {
                        "course_id": cid,
                        "course_name": course_name,
                        "entry_id": entry_id,
                        "class_name": entry.get('class_name', ''),
                        "instructor": "",
                        "hours": 0,
                        "is_holiday": True,
                    }
                }
            else:
                start_time = entry.get('start_time', '09:00')
                end_time = entry.get('end_time', '18:00')
                instructor = entry.get('instructor', '')
                class_name = entry.get('class_name', '')
                title = f"({instructor}) {class_name}" if instructor else class_name
                event = {
                    "id": entry_id or f"{cid}_{date}",
                    "title": title,
                    "start": f"{date}T{start_time}:00",
                    "end": f"{date}T{end_time}:00",
                    "color": color,
                    "textColor": "#ffffff",
                    "extendedProps": {
                        "course_id": cid,
                        "course_name": course_name,
                        "entry_id": entry_id,
                        "class_name": class_name,
                        "instructor": entry.get('instructor', ''),
                        "hours": entry.get('hours', 0),
                        "is_holiday": False,
                    }
                }
            events.append(event)

    return events


def get_course_stats(courses):
    """과정별 통계 계산"""
    stats = []
    for course in courses:
        entries = course.get('entries', [])
        total_entries = len(entries)
        class_entries = [e for e in entries if not e.get('is_holiday', False)]
        holiday_entries = [e for e in entries if e.get('is_holiday', False)]
        total_hours = sum(e.get('hours', 0) for e in class_entries)

        # 강사별 수업 수 (쉼표로 구분된 복수 강사 개별 집계)
        instructor_counts = defaultdict(int)
        for e in class_entries:
            instructor = e.get('instructor', '')
            if instructor:
                for name in instructor.split(','):
                    name = name.strip()
                    if name:
                        instructor_counts[name] += 1

        # 날짜 범위
        dates = sorted([e.get('date', '') for e in entries if e.get('date')])
        date_range = f"{dates[0]} ~ {dates[-1]}" if dates else ""

        stats.append({
            "course_id": course.get('id'),
            "course_name": course.get('name'),
            "color": course.get('color'),
            "total_classes": len(class_entries),
            "total_holidays": len(holiday_entries),
            "total_hours": total_hours,
            "date_range": date_range,
            "instructors": dict(instructor_counts),
        })

    return stats
