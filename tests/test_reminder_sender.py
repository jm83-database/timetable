import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from services import reminder_attachments, reminder_sender
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
    assert all('결과보고서' not in call[3] for call in calls)
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
    assert 'attachments' not in calls[0][1]['json']['message']
    Response.status_code = 403
    assert send('sender@example.com', 'token', 'user@gmail.com', 'subject', 'body') == 'failed'
    Response.status_code = 503
    assert send('sender@example.com', 'token', 'user@gmail.com', 'subject', 'body') == 'uncertain'


def test_bundled_attachments_are_complete_and_fit_graph_request_limit():
    attachments = reminder_attachments.load_attachments('short_term')
    assert len(attachments) == 2
    for attachment, (name, content_type) in zip(attachments, reminder_attachments.ATTACHMENT_FILES):
        assert attachment['@odata.type'] == '#microsoft.graph.fileAttachment'
        assert attachment['name'] == name
        assert attachment['contentType'] == content_type
        raw = base64.b64decode(attachment['contentBytes'], validate=True)
        assert raw == (reminder_attachments.ATTACHMENT_DIR / name).read_bytes()
        assert raw.startswith(b'%PDF-' if name.endswith('.pdf') else b'PK')
        assert len(raw) < 3 * 1024 * 1024
    payload = {'message': {'subject': '수업 준비 안내', 'body': {'contentType': 'Text', 'content': '안내'},
                           'toRecipients': [{'emailAddress': {'address': 'user@gmail.com'}}],
                           'attachments': attachments}, 'saveToSentItems': True}
    assert len(json.dumps(payload).encode('utf-8')) < 4 * 1024 * 1024


@pytest.mark.parametrize('offset', [7, 3])
def test_short_term_cycle_sends_both_files_to_each_recipient_only_once(tmp_path, monkeypatch, offset):
    store = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    first = store.add_contact('담당자', 'person@naver.com')
    second = store.add_contact('강사', 'teacher@gmail.com')
    store.save_assignment('course', 'lesson', [first['id'], second['id']], 'short_term')
    due = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)
    courses = [{'id': 'course', 'entries': [
        {'id': 'lesson', 'date': (due.date() + timedelta(days=offset)).isoformat()},
    ]}]
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs['json'])
        return type('Response', (), {'status_code': 202})()

    monkeypatch.setattr(reminder_sender.requests, 'post', post)
    assert run_reminder_cycle(courses, store, 'sender', 'token', due) == 2
    assert run_reminder_cycle(courses, store, 'sender', 'token', due) == 0
    assert len(calls) == 2
    assert {call['message']['toRecipients'][0]['emailAddress']['address'] for call in calls} == {
        first['email'], second['email'],
    }
    for call in calls:
        message = call['message']
        assert f'D-{offset}' in message['subject']
        assert '첨부된 결과보고서 견본과 양식' in message['body']['content']
        assert '교육 종료 후 결과보고서 작성을 부탁드립니다.' in message['body']['content']
        assert '우수 산출물(수강후기)을 5개 이상 포함' in message['body']['content']
        assert 'Padlet에 올라온 수강후기가 5개 미만이라면, 올라온 내용을 최대한 많이 포함' in message['body']['content']
        assert message['attachments'] == reminder_attachments.load_attachments('short_term')
    store.save_assignment('course', 'lesson', [first['id'], second['id']], 'regular')
    assert run_reminder_cycle(courses, store, 'sender', 'token', due) == 0


@pytest.mark.parametrize('failure', ['missing', 'empty'])
def test_attachment_failure_blocks_send_and_retries_after_file_repair(tmp_path, monkeypatch, caplog, failure):
    attachment_dir = tmp_path / 'attachments'
    attachment_dir.mkdir()
    monkeypatch.setattr(reminder_attachments, 'ATTACHMENT_DIR', attachment_dir)
    first, second = [name for name, _ in reminder_attachments.ATTACHMENT_FILES]
    (attachment_dir / first).write_bytes(b'%PDF-test')
    if failure == 'empty':
        (attachment_dir / second).write_bytes(b'')
    store = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    contact = store.add_contact('담당자', 'person@naver.com')
    store.save_assignment('course', 'lesson', [contact['id']], 'short_term')
    courses = [{'id': 'course', 'entries': [{'id': 'lesson', 'date': '2026-10-31'}]}]
    due = datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)
    calls = []

    def send(*args, **kwargs):
        calls.append(kwargs['attachments'])
        return 'accepted'

    assert run_reminder_cycle(courses, store, 'sender', 'token', due, send) == 1
    assert calls == []
    assert store.deliveries('course', 'lesson')[0]['status'] == 'failed'
    assert 'Reminder attachment preparation failed' in caplog.text
    assert run_reminder_cycle(courses, store, 'sender', 'token', due, send) == 0
    (attachment_dir / second).write_bytes(b'PK-test')
    assert run_reminder_cycle(courses, store, 'sender', 'token', due + timedelta(hours=1), send) == 1
    assert len(calls) == 1 and len(calls[0]) == 2
    delivery = store.deliveries('course', 'lesson')[0]
    assert delivery['status'] == 'accepted'
    assert delivery['attempt_count'] == 2


def test_regular_reminder_needs_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(reminder_attachments, 'ATTACHMENT_DIR', tmp_path / 'missing')
    assert reminder_attachments.load_attachments('regular') == []
    with pytest.raises(ValueError, match='교육 유형'):
        reminder_attachments.load_attachments('unknown')