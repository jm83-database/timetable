import pytest

from app import create_app
from services.reminder_storage import LocalReminderStorage
import routes_reminders
import services.cosmos_service
import services.reminder_storage


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    monkeypatch.setattr(routes_reminders, 'get_reminder_storage', lambda: storage)

    class CourseStorage:
        def get_all_courses(self):
            return [{'id': 'course', 'entries': [
                {'id': 'lesson'}, {'id': 'holiday', 'is_holiday': True},
            ]}]

    monkeypatch.setattr(routes_reminders, 'get_storage', CourseStorage)
    app = create_app()
    app.config.update(TESTING=True, AUTH_MODE='local', WEBSITE_SITE_NAME='')
    return app.test_client()


def test_external_contacts_and_class_assignments(client):
    created = client.post('/api/reminders/contacts', json={'name': '담당자', 'email': 'user@naver.com'})
    assert created.status_code == 201
    contact_id = created.json['contact']['id']
    path = '/api/reminders/courses/course/entries/lesson'
    assert client.put(path, json={'recipients': [contact_id]}).status_code == 200
    assert client.get(path).json['recipients'] == [contact_id]
    assert client.delete('/api/reminders/contacts/' + contact_id).status_code == 409
    assert client.put(path, json={'recipients': []}).status_code == 200
    assert client.delete('/api/reminders/contacts/' + contact_id).status_code == 200


def test_rejects_invalid_input_and_unknown_or_holiday_entries(client):
    assert client.post('/api/reminders/contacts', json={'name': 'x', 'email': 'not-an-email'}).status_code == 400
    assert client.post('/api/reminders/contacts', json=[]).status_code == 400
    path = '/api/reminders/courses/course/entries/lesson'
    assert client.put(path, json={'recipients': ['unknown']}).status_code == 400
    assert client.put(path, json={'recipients': [1]}).status_code == 400
    assert client.get('/api/reminders/courses/course/entries/holiday').status_code == 404
    assert client.get('/api/reminders/courses/course/entries/missing').status_code == 404


def test_changing_class_to_holiday_clears_its_assignment(tmp_path, monkeypatch):
    storage = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    contact = storage.add_contact('담당자', 'person@naver.com')
    storage.save_assignment('course', 'lesson', [contact['id']])
    monkeypatch.setattr(services.reminder_storage, 'get_reminder_storage', lambda: storage)
    monkeypatch.setattr(services.cosmos_service, 'get_storage', lambda: type('Storage', (), {
        'update_entry': lambda self, course_id, entry_id, updates: True,
    })())
    app = create_app()
    app.config.update(TESTING=True, AUTH_MODE='local', WEBSITE_SITE_NAME='')

    response = app.test_client().put('/api/courses/course/entries/lesson', json={
        'date': '2026-10-28', 'class_name': '휴일', 'is_holiday': True,
        'start_time': '09:00', 'end_time': '18:00',
    })

    assert response.status_code == 200
    assert storage.assignment('course', 'lesson')['recipients'] == []
    assert storage.delete_contact(contact['id'])