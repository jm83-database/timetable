"""Contact and per-class reminder configuration storage."""

import hashlib
import json
import os
import threading
from datetime import datetime, timedelta

from config import Config


_storage = None


def _key(prefix, *parts):
    value = json.dumps(parts, ensure_ascii=False, separators=(',', ':'))
    return prefix + hashlib.sha256(value.encode('utf-8')).hexdigest()


def _retry_document(existing, attempted_at):
    if not existing or existing.get('status') != 'failed':
        return None
    previous = datetime.fromisoformat(existing['attempted_at'])
    current = datetime.fromisoformat(attempted_at)
    if current - previous < timedelta(hours=1):
        return None
    return {**existing, 'status': 'sending', 'attempted_at': attempted_at,
            'attempt_count': existing.get('attempt_count', 1) + 1}


def get_reminder_storage():
    global _storage
    if _storage is None:
        if Config.use_cosmos_db():
            from services.cosmos_service import get_storage
            _storage = CosmosReminderStorage(get_storage().container)
        else:
            _storage = LocalReminderStorage(os.path.join(Config.DATA_DIR, 'reminders.json'))
    return _storage


class ReminderStorage:
    def contacts(self):
        return sorted(self._list('reminder_contact'), key=lambda item: item['name'].casefold())

    def add_contact(self, name, email):
        contact = {
            'id': _key('contact_', email.casefold()),
            'type': 'reminder_contact',
            'name': name,
            'email': email,
        }
        self._create(contact)
        return contact

    def delete_contact(self, contact_id):
        if any(contact_id in item.get('recipients', []) for item in self._list('reminder_assignment')):
            raise ValueError('수업에 지정된 수신자는 먼저 지정 해제해주세요.')
        return self._delete('reminder_contact', contact_id)

    def assignment(self, course_id, entry_id):
        key = _key('assignment_', course_id, entry_id)
        return self._get('reminder_assignment', key) or {
            'id': key, 'type': 'reminder_assignment',
            'course_id': course_id, 'entry_id': entry_id, 'recipients': [],
        }

    def save_assignment(self, course_id, entry_id, recipients):
        contact_ids = {contact['id'] for contact in self.contacts()}
        if not set(recipients).issubset(contact_ids):
            raise ValueError('등록되지 않은 수신자가 있습니다.')
        assignment = self.assignment(course_id, entry_id)
        assignment['recipients'] = list(dict.fromkeys(recipients))
        self._put(assignment)
        return assignment

    def delete_assignment(self, course_id, entry_id):
        return self._delete('reminder_assignment', _key('assignment_', course_id, entry_id))

    def delete_course_assignments(self, course_id):
        for assignment in self._list('reminder_assignment'):
            if assignment.get('course_id') == course_id:
                self._delete('reminder_assignment', assignment['id'])

    def begin_delivery(self, course_id, entry_id, class_date, offset, contact_id, attempted_at):
        delivery = {
            'id': _key('delivery_', course_id, entry_id, class_date, str(offset), contact_id),
            'type': 'reminder_delivery', 'course_id': course_id, 'entry_id': entry_id,
            'class_date': class_date, 'offset': offset, 'contact_id': contact_id,
            'status': 'sending', 'attempted_at': attempted_at, 'attempt_count': 1,
        }
        try:
            self._create(delivery)
        except ValueError:
            return self._retry(delivery['id'], attempted_at)
        return delivery

    def finish_delivery(self, delivery, status):
        if status not in ('accepted', 'failed', 'uncertain'):
            raise ValueError('Invalid delivery status')
        self._put({**delivery, 'status': status})

    def deliveries(self, course_id, entry_id):
        return [item for item in self._list('reminder_delivery')
                if item.get('course_id') == course_id and item.get('entry_id') == entry_id]


class LocalReminderStorage(ReminderStorage):
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()

    def _load(self):
        try:
            with open(self.path, encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def _save(self, data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        temporary = self.path + '.tmp'
        with open(temporary, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temporary, self.path)

    def _list(self, kind):
        with self.lock:
            return list(self._load().get(kind, {}).values())

    def _get(self, kind, key):
        with self.lock:
            return self._load().get(kind, {}).get(key)

    def _create(self, document):
        with self.lock:
            data = self._load()
            items = data.setdefault(document['type'], {})
            if document['id'] in items:
                raise ValueError('이미 등록된 이메일 주소입니다.')
            items[document['id']] = document
            self._save(data)

    def _put(self, document):
        with self.lock:
            data = self._load()
            data.setdefault(document['type'], {})[document['id']] = document
            self._save(data)

    def _delete(self, kind, key):
        with self.lock:
            data = self._load()
            if key not in data.get(kind, {}):
                return False
            del data[kind][key]
            self._save(data)
            return True

    def _retry(self, key, attempted_at):
        with self.lock:
            data = self._load()
            items = data.get('reminder_delivery', {})
            delivery = _retry_document(items.get(key), attempted_at)
            if delivery is not None:
                items[key] = delivery
                self._save(data)
            return delivery


class CosmosReminderStorage(ReminderStorage):
    def __init__(self, container):
        self.container = container

    def deliveries(self, course_id, entry_id):
        return list(self.container.query_items(
             query=('SELECT * FROM c WHERE c.type = @type '
                 'AND c.course_id = @course_id AND c.entry_id = @entry_id'),
            parameters=[{'name': '@type', 'value': 'reminder_delivery'},
                        {'name': '@course_id', 'value': course_id},
                        {'name': '@entry_id', 'value': entry_id}],
            partition_key='reminder_delivery',
        ))

    def _list(self, kind):
        return list(self.container.query_items(
            query='SELECT * FROM c WHERE c.type = @type',
            parameters=[{'name': '@type', 'value': kind}],
            partition_key=kind,
        ))

    def _get(self, kind, key):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        try:
            return self.container.read_item(item=key, partition_key=kind)
        except CosmosResourceNotFoundError:
            return None

    def _create(self, document):
        from azure.cosmos.exceptions import CosmosResourceExistsError
        try:
            self.container.create_item(body=document)
        except CosmosResourceExistsError as error:
            raise ValueError('이미 등록된 이메일 주소입니다.') from error

    def _put(self, document):
        self.container.upsert_item(body=document)

    def _delete(self, kind, key):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        try:
            self.container.delete_item(item=key, partition_key=kind)
            return True
        except CosmosResourceNotFoundError:
            return False

    def _retry(self, key, attempted_at):
        from azure.core import MatchConditions
        from azure.cosmos.exceptions import CosmosHttpResponseError
        existing = self._get('reminder_delivery', key)
        delivery = _retry_document(existing, attempted_at)
        if delivery is None:
            return None
        try:
            self.container.replace_item(item=key, body=delivery, etag=existing['_etag'],
                                        match_condition=MatchConditions.IfNotModified)
        except CosmosHttpResponseError as error:
            if error.status_code in (404, 412):
                return None
            raise
        return delivery