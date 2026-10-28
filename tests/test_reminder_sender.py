from datetime import datetime, timedelta, timezone

from services import reminder_sender
from services.reminder_sender import run_reminder_cycle
from services.reminder_storage import LocalReminderStorage


def test_sends_separately_and_only_once_on_each_due_day(tmp_path):
    store = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    first = store.add_contact('담당자', 'person@naver.com')
    second = store.add_contact('강사', 'teacher@gmail.com')
    store.save_assignment('course', 'lesson', [first['id'], second['id']])
    courses = [{'id': 'course', 'name': '교육', 'entries': [
        {'id': 'lesson', 'date': '2026-11-04', 'class_name': '수업', 'instructor': '강사',
         'start_time': '09:00', 'end_time': '18:00'},
    ]}]
    calls = []

    def send(sender, token, address, subject, body):
        calls.append((sender, address, subject, body))
        return 'accepted'

    now = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)
    assert run_reminder_cycle(courses, store, 'elixirr@elixirr.co.kr', 'token', now, send) == 2
    assert run_reminder_cycle(courses, store, 'elixirr@elixirr.co.kr', 'token', now, send) == 0
    assert {call[1] for call in calls} == {'person@naver.com', 'teacher@gmail.com'}
    assert all('D-7' in call[2] and '2026-11-04' in call[3] for call in calls)
    assert {item['status'] for item in store.deliveries('course', 'lesson')} == {'accepted'}


def test_does_not_retry_uncertain_result_and_waits_until_nine(tmp_path):
    store = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    contact = store.add_contact('담당자', 'person@gmail.com')
    store.save_assignment('course', 'lesson', [contact['id']])
    courses = [{'id': 'course', 'entries': [{'id': 'lesson', 'date': '2026-10-31'}]}]

    def failed_send(*args):
        raise TimeoutError('outcome unknown')

    early = datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)
    due = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)
    assert run_reminder_cycle(courses, store, 'sender', 'token', early, failed_send) == 0
    assert run_reminder_cycle(courses, store, 'sender', 'token', due, failed_send) == 1
    assert run_reminder_cycle(courses, store, 'sender', 'token', due, failed_send) == 0
    assert store.deliveries('course', 'lesson')[0]['status'] == 'uncertain'


def test_retries_explicit_rejection_after_one_hour(tmp_path):
    store = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    contact = store.add_contact('담당자', 'person@gmail.com')
    store.save_assignment('course', 'lesson', [contact['id']])
    courses = [{'id': 'course', 'entries': [{'id': 'lesson', 'date': '2026-10-31'}]}]
    outcomes = iter(['failed', 'accepted'])
    send = lambda *args: next(outcomes)
    due = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)

    assert run_reminder_cycle(courses, store, 'sender', 'token', due, send) == 1
    assert run_reminder_cycle(courses, store, 'sender', 'token', due, send) == 0
    assert run_reminder_cycle(courses, store, 'sender', 'token', due + timedelta(hours=1), send) == 1
    delivery = store.deliveries('course', 'lesson')[0]
    assert delivery['status'] == 'accepted'
    assert delivery['attempt_count'] == 2


def test_graph_receives_one_external_recipient_and_classifies_results(monkeypatch):
    calls = []

    class Response:
        status_code = 202

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(reminder_sender.requests, 'post', post)
    send = reminder_sender.send_graph_mail
    assert send('elixirr@elixirr.co.kr', 'token', 'user@gmail.com', 'subject', 'body') == 'accepted'
    assert calls[0][1]['json']['message']['toRecipients'] == [{'emailAddress': {'address': 'user@gmail.com'}}]
    Response.status_code = 403
    assert send('sender@example.com', 'token', 'user@gmail.com', 'subject', 'body') == 'failed'
    Response.status_code = 503
    assert send('sender@example.com', 'token', 'user@gmail.com', 'subject', 'body') == 'uncertain'