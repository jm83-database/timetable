"""Send scheduled reminders and retain a conservative delivery record."""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

from services.reminder_attachments import load_attachments
from services.reminder_schedule import due_classes


logger = logging.getLogger(__name__)
KOREA_TIME = timezone(timedelta(hours=9))


def message_for(course, entry, offset):
    subject = f"[수업 준비 안내 D-{offset}] {course.get('name', '')} - {entry.get('class_name', '')}"
    body = '\n'.join([
        '안녕하세요. 수업 준비를 위한 안내입니다.', '',
        f"과정: {course.get('name', '')}",
        f"수업: {entry.get('class_name', '')}",
        f"날짜: {entry.get('date', '')}",
        f"시간: {entry.get('start_time', '')} ~ {entry.get('end_time', '')}",
        f"강사: {entry.get('instructor') or '미정'}", '',
        '수업 준비를 부탁드립니다.',
    ])
    return subject, body


def send_graph_mail(sender, token, address, subject, body, attachments=None):
    message = {'subject': subject, 'body': {'contentType': 'Text', 'content': body},
               'toRecipients': [{'emailAddress': {'address': address}}]}
    if attachments:
        message['attachments'] = attachments
    response = requests.post(
        f'https://graph.microsoft.com/v1.0/users/{quote(sender, safe="")}/sendMail',
        headers={'Authorization': f'Bearer {token}'},
        json={'message': message, 'saveToSentItems': True},
        timeout=(5, 15),
    )
    if response.status_code == 202:
        return 'accepted'
    logger.warning('Graph reminder request returned HTTP %s', response.status_code)
    if 400 <= response.status_code < 500 and response.status_code != 408:
        return 'failed'
    return 'uncertain'


def run_reminder_cycle(courses, storage, sender, token, now=None, send=send_graph_mail):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('An aware datetime is required')
    local_now = now.astimezone(KOREA_TIME)
    if local_now.hour < 9:
        return 0
    contacts = {contact['id']: contact for contact in storage.contacts()}
    count = 0
    for course, entry, offset in due_classes(courses, local_now.date()):
        assignment = storage.assignment(course['id'], entry['id'])
        attachments = None
        for contact_id in assignment['recipients']:
            contact = contacts.get(contact_id)
            if not contact:
                logger.error('Reminder contact is missing for entry %s', entry['id'])
                continue
            delivery = storage.begin_delivery(course['id'], entry['id'], entry['date'], offset,
                                              contact_id, now.astimezone(timezone.utc).isoformat())
            if delivery is None:
                continue
            subject, body = message_for(course, entry, offset)
            try:
                if attachments is None:
                    attachments = load_attachments(assignment['education_type'])
            except (OSError, ValueError):
                logger.exception('Reminder attachment preparation failed: %s', delivery['id'])
                storage.finish_delivery(delivery, 'failed')
                count += 1
                continue
            if attachments:
                body += '\n\n첨부된 결과보고서 견본과 양식을 확인해주세요.'
            try:
                if attachments:
                    status = send(sender, token, contact['email'], subject, body,
                                  attachments=attachments)
                else:
                    status = send(sender, token, contact['email'], subject, body)
            except Exception:
                logger.exception('Reminder delivery outcome is uncertain: %s', delivery['id'])
                status = 'uncertain'
            storage.finish_delivery(delivery, status)
            count += 1
    return count