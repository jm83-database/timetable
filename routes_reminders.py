"""APIs for reusable reminder contacts and per-class assignments."""

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, jsonify, request

from services.cosmos_service import get_storage
from services.reminder_attachments import EDUCATION_TYPES
from services.reminder_storage import get_reminder_storage


reminder_bp = Blueprint('reminders', __name__, url_prefix='/api/reminders')


def _entry_exists(course_id, entry_id):
    for course in get_storage().get_all_courses():
        if course.get('id') == course_id:
            return any(entry.get('id') == entry_id and not entry.get('is_holiday')
                       for entry in course.get('entries', []))
    return False


@reminder_bp.route('/contacts', methods=['GET', 'POST'])
def contacts():
    storage = get_reminder_storage()
    if request.method == 'GET':
        return jsonify({'success': True, 'contacts': [
            {key: contact[key] for key in ('id', 'name', 'email')}
            for contact in storage.contacts()
        ]})

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'success': False, 'error': '잘못된 요청입니다.'}), 400
    name = data.get('name')
    email = data.get('email')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return jsonify({'success': False, 'error': '이름은 1~100자로 입력해주세요.'}), 400
    if not isinstance(email, str) or len(email) > 254:
        return jsonify({'success': False, 'error': '이메일 주소를 확인해주세요.'}), 400
    try:
        email = validate_email(email.strip(), check_deliverability=False).normalized
        contact = storage.add_contact(name.strip(), email)
    except (EmailNotValidError, ValueError) as error:
        return jsonify({'success': False, 'error': str(error)}), 400
    return jsonify({'success': True, 'contact': {
        key: contact[key] for key in ('id', 'name', 'email')
    }}), 201


@reminder_bp.route('/contacts/<contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    try:
        deleted = get_reminder_storage().delete_contact(contact_id)
    except ValueError as error:
        return jsonify({'success': False, 'error': str(error)}), 409
    if not deleted:
        return jsonify({'success': False, 'error': '수신자를 찾을 수 없습니다.'}), 404
    return jsonify({'success': True})


@reminder_bp.route('/courses/<course_id>/entries/<entry_id>', methods=['GET', 'PUT'])
def assignment(course_id, entry_id):
    if not _entry_exists(course_id, entry_id):
        return jsonify({'success': False, 'error': '수업 일정을 찾을 수 없습니다.'}), 404
    storage = get_reminder_storage()
    if request.method == 'GET':
        deliveries = storage.deliveries(course_id, entry_id)
        saved = storage.assignment(course_id, entry_id)
        return jsonify({'success': True, 'recipients': saved['recipients'],
                        'education_type': saved['education_type'],
                        'deliveries': [{key: item[key] for key in ('class_date', 'offset', 'contact_id', 'status', 'attempted_at')}
                                       for item in deliveries]})

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'error': '수신자 목록을 확인해주세요.'}), 400
    recipients = data.get('recipients')
    if (not isinstance(recipients, list) or len(recipients) > 100
            or any(not isinstance(item, str) or len(item) > 80 for item in recipients)):
        return jsonify({'success': False, 'error': '수신자 목록을 확인해주세요.'}), 400
    education_type = data.get('education_type')
    if 'education_type' in data and (
            not isinstance(education_type, str) or education_type not in EDUCATION_TYPES):
        return jsonify({'success': False, 'error': '교육 유형을 확인해주세요.'}), 400
    try:
        result = storage.save_assignment(course_id, entry_id, recipients, education_type)
    except ValueError as error:
        return jsonify({'success': False, 'error': str(error)}), 400
    return jsonify({'success': True, 'recipients': result['recipients'],
                    'education_type': result['education_type']})