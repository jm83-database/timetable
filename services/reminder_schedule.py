"""Select class entries due for preparation reminders."""

from datetime import date, datetime, timedelta


REMINDER_OFFSETS = (7, 3)


def due_classes(courses, today):
    if not isinstance(today, date) or isinstance(today, datetime):
        raise TypeError("today must be a date")

    dates = {
        (today + timedelta(days=offset)).isoformat(): offset
        for offset in REMINDER_OFFSETS
    }
    for course in courses:
        for entry in course.get('entries', []):
            offset = dates.get(entry.get('date'))
            if offset and not entry.get('is_holiday') and entry.get('id'):
                yield course, entry, offset