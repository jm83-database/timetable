import pytest

from services.reminder_storage import CosmosReminderStorage, LocalReminderStorage


def test_contacts_are_reusable_and_assignments_are_per_class(tmp_path):
    store = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    first = store.add_contact('담당자', 'person@naver.com')
    second = store.add_contact('강사', 'teacher@gmail.com')

    store.save_assignment('course-a', 'entry-a', [first['id'], second['id'], first['id']])
    store.save_assignment('course-a', 'entry-b', [first['id']])

    reopened = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    assert reopened.assignment('course-a', 'entry-a')['recipients'] == [first['id'], second['id']]
    assert reopened.assignment('course-a', 'entry-b')['recipients'] == [first['id']]
    assert reopened.assignment('course-b', 'entry-a')['recipients'] == []


def test_rejects_duplicate_and_unknown_contacts_and_prevents_orphans(tmp_path):
    store = LocalReminderStorage(str(tmp_path / 'reminders.json'))
    contact = store.add_contact('담당자', 'person@naver.com')
    with pytest.raises(ValueError):
        store.add_contact('다른 이름', 'PERSON@NAVER.COM')
    with pytest.raises(ValueError):
        store.save_assignment('course', 'entry', ['unknown'])
    store.save_assignment('course', 'entry', [contact['id']])
    with pytest.raises(ValueError):
        store.delete_contact(contact['id'])
    store.save_assignment('course', 'entry', [])
    assert store.delete_contact(contact['id'])
    assert not store.delete_contact(contact['id'])


def test_cosmos_delivery_history_queries_only_the_requested_class():
    class Container:
        def query_items(self, **kwargs):
            self.query = kwargs
            return []

    container = Container()
    assert CosmosReminderStorage(container).deliveries('course', 'entry') == []
    assert container.query['partition_key'] == 'reminder_delivery'
    assert container.query['parameters'] == [
        {'name': '@type', 'value': 'reminder_delivery'},
        {'name': '@course_id', 'value': 'course'},
        {'name': '@entry_id', 'value': 'entry'},
    ]


def test_cosmos_retry_claim_uses_etag_and_rejects_conflict():
    from azure.core import MatchConditions
    from azure.cosmos.exceptions import CosmosHttpResponseError

    class Container:
        conflict = False

        def read_item(self, item, partition_key):
            return {'id': item, 'type': partition_key, 'status': 'failed',
                    'attempted_at': '2026-10-28T00:00:00+00:00', '_etag': 'etag'}

        def replace_item(self, **kwargs):
            self.options = kwargs
            if self.conflict:
                raise CosmosHttpResponseError(status_code=412)

    container = Container()
    store = CosmosReminderStorage(container)
    claimed = store._retry('delivery', '2026-10-28T01:00:00+00:00')
    assert claimed['status'] == 'sending'
    assert container.options['etag'] == 'etag'
    assert container.options['match_condition'] == MatchConditions.IfNotModified
    container.conflict = True
    assert store._retry('delivery', '2026-10-28T01:00:00+00:00') is None