"""Tests for preparation reminder dates."""

import unittest
from datetime import date, datetime

from services.reminder_schedule import due_classes


class ReminderScheduleTests(unittest.TestCase):
    def test_selects_each_class_seven_or_three_calendar_days_ahead(self):
        courses = [{
            'id': 'course',
            'entries': [
                {'id': 'week', 'date': '2026-11-04'},
                {'id': 'three', 'date': '2026-10-31'},
                {'id': 'same-date', 'date': '2026-10-31'},
                {'id': 'other', 'date': '2026-11-03'},
                {'id': 'holiday', 'date': '2026-10-31', 'is_holiday': True},
                {'date': '2026-10-31'},
            ],
        }]

        result = list(due_classes(courses, date(2026, 10, 28)))

        self.assertEqual([(entry['id'], offset) for _, entry, offset in result], [
            ('week', 7), ('three', 3), ('same-date', 3),
        ])

    def test_requires_an_explicit_date(self):
        with self.assertRaises(TypeError):
            list(due_classes([], '2026-10-28'))
        with self.assertRaises(TypeError):
            list(due_classes([], datetime(2026, 10, 28)))


if __name__ == '__main__':
    unittest.main()