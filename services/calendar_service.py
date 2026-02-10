"""
FullCalendar 이벤트 포맷 변환 서비스
"""
from collections import defaultdict


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
