"""
Timetable Dashboard - 라우트 정의
"""
import re
import logging
from urllib.parse import urlsplit
from flask import Blueprint, render_template, jsonify, request, send_file

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')

# 입력 검증 유틸리티
HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _validate_color(color):
    return bool(HEX_COLOR_RE.match(color)) if color else False


def _validate_time(t):
    return bool(TIME_RE.match(t)) if t else False


def _sanitize_name(name, max_len=50):
    """공백 제거 후 max_len까지 자름 (None이면 길이 제한 없음)"""
    return name.strip()[:max_len] if name else ''


def _normalize_instructor(value, max_len=50):
    """'정종현, 이정환' / '정종현/이정환' → '정종현,이정환' (저장 형식: 쉼표만, 공백·중복 제거)"""
    names = [n.strip() for n in re.split(r'[,/]', value or '') if n.strip()]
    return ','.join(dict.fromkeys(names))[:max_len]


def _resolve_class_time(data):
    """start_time + (end_time | hours) → (hours, start_time, end_time). 종료 시각이 있으면 분 단위로 수업시간 계산. 오류 시 ValueError"""
    from services.excel_parser import calculate_end_time, calculate_hours, normalize_hours

    start_time = data.get('start_time', '09:00')
    if not _validate_time(start_time):
        start_time = '09:00'

    end_time = data.get('end_time')
    if end_time:
        if not _validate_time(end_time):
            raise ValueError("종료 시각 형식이 올바르지 않습니다. (HH:MM)")
        hours = calculate_hours(start_time, end_time)
        if hours is None:
            raise ValueError("종료 시각은 시작 시각보다 늦어야 합니다.")
    else:
        hours = normalize_hours(data.get('hours', 8))
        if hours is None:
            raise ValueError("수업시간은 숫자로 입력해주세요. (예: 4.5)")
        end_time = calculate_end_time(start_time, hours)

    if not 0 < hours <= 12:
        raise ValueError("수업시간은 0보다 크고 12시간 이하여야 합니다.")
    return hours, start_time, end_time


LOCATION_TYPES = ('online', 'offline')
LOCATION_MAX_LEN = 200
LINK_MAX_LEN = 2048


def _resolve_location(data):
    """location_type + location → 저장 필드. 오프라인은 장소 필수. 오류 시 ValueError"""
    location_type = data.get('location_type', 'online')
    if location_type not in LOCATION_TYPES:
        raise ValueError("수업 장소 구분을 확인해주세요. (online/offline)")
    if location_type == 'online':
        return {'location_type': 'online', 'location': ''}
    location = _sanitize_name(str(data.get('location') or ''), max_len=None)
    if not location:
        raise ValueError("오프라인 수업은 장소(기관명 또는 주소)를 입력해주세요.")
    if len(location) > LOCATION_MAX_LEN:
        raise ValueError(f"수업 장소는 {LOCATION_MAX_LEN}자 이하로 입력해주세요.")
    return {'location_type': 'offline', 'location': location}


def _resolve_optional_url(value, label):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValueError(f"{label}은 http 또는 https URL을 입력해주세요.")
    url = value.strip()
    if not url:
        return ''
    if len(url) > LINK_MAX_LEN or any(char.isspace() for char in url):
        raise ValueError(f"{label}은 유효한 http 또는 https URL을 입력해주세요.")
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in ('http', 'https') or not parts.hostname:
            raise ValueError
        parts.port
    except ValueError as error:
        raise ValueError(f"{label}은 유효한 http 또는 https URL을 입력해주세요.") from error
    return url


def _resolve_class_links(data, location_type):
    return {
        'course_material_url': _resolve_optional_url(data.get('course_material_url', ''), '강의자료 링크'),
        'online_class_url': _resolve_optional_url(
            data.get('online_class_url', '') if location_type == 'online' else '',
            '온라인 수업 링크',
        ),
    }


# ===== 페이지 라우트 =====

@main_bp.route('/')
def index():
    return render_template('dashboard.html')


@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@main_bp.route('/upload')
def upload_page():
    return render_template('upload.html')


# ===== API 라우트 =====

@api_bp.route('/courses', methods=['GET'])
def get_courses():
    """전체 과정 목록 반환 (entries 제외, 메타데이터만)"""
    from services.cosmos_service import get_storage
    storage = get_storage()
    return jsonify({"success": True, "courses": storage.get_course_summaries()})


@api_bp.route('/events', methods=['GET'])
def get_events():
    """FullCalendar 이벤트 JSON 반환"""
    from services.cosmos_service import get_storage
    from services.calendar_service import format_events
    storage = get_storage()
    course_id = request.args.get('course_id')
    courses = storage.get_all_courses()
    events = format_events(courses, course_id)
    return jsonify(events)


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """과정별 통계 반환"""
    from services.cosmos_service import get_storage
    from services.calendar_service import get_course_stats
    storage = get_storage()
    courses = storage.get_all_courses()
    stats = get_course_stats(courses)
    return jsonify({"success": True, "stats": stats})


@api_bp.route('/sheets', methods=['POST'])
def get_sheets():
    """엑셀 파일 업로드 후 시트 목록 반환"""
    from services.excel_parser import detect_timetable_format, get_sheet_names
    import os
    from config import Config

    if 'file' not in request.files:
        return jsonify({"success": False, "error": "파일이 없습니다."}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "파일이 선택되지 않았습니다."}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in Config.ALLOWED_EXTENSIONS:
        return jsonify({"success": False, "error": "xlsx 또는 xls 파일만 업로드 가능합니다."}), 400

    import uuid as _uuid
    # secure_filename은 한글을 모두 제거하므로('직원근무표.xlsx' → 'xlsx') 유니코드 문자를 보존하며 직접 정제
    stem = re.sub(r'[^\w-]+', '_', file.filename.rsplit('.', 1)[0]).strip('._') or 'upload'
    safe_name = f"{_uuid.uuid4().hex[:8]}_{stem[:80]}.{ext}"
    filepath = os.path.join(Config.UPLOAD_FOLDER, safe_name)
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    file.save(filepath)

    # 실제 엑셀 파일인지 검증
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True)
        wb.close()
    except Exception as e:
        logger.warning(f"엑셀 파일 검증 실패 ({file.filename}): {e}")
        try:
            os.remove(filepath)
        except OSError:
            pass
        return jsonify({"success": False, "error": "유효한 엑셀 파일이 아닙니다."}), 400

    try:
        timetable_format = detect_timetable_format(filepath)
        sheets = [] if timetable_format == 'multi_course' else get_sheet_names(filepath)
        if timetable_format != 'multi_course' and not sheets:
            os.remove(filepath)
            return jsonify({"success": False, "error": "유효한 시트를 찾을 수 없습니다."}), 400
        return jsonify({
            "success": True,
            "sheets": sheets,
            "filepath": filepath,
            "format": timetable_format,
        })
    except Exception as e:
        logger.error(f"엑셀 파일 읽기 실패: {e}", exc_info=True)
        try:
            os.remove(filepath)
        except OSError:
            pass
        return jsonify({"success": False, "error": "엑셀 파일을 읽을 수 없습니다. 파일 형식을 확인해주세요."}), 400


@api_bp.route('/templates/multi-course.xlsx', methods=['GET'])
def download_multi_course_template():
    """한 표에 여러 과정의 수업을 입력하는 템플릿 다운로드"""
    from services.excel_parser import create_multi_course_template

    return send_file(
        create_multi_course_template(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='multi_course_timetable_template.xlsx',
    )


@api_bp.route('/upload', methods=['POST'])
def upload_course():
    """엑셀 파싱 후 과정 저장"""
    from services.excel_parser import detect_timetable_format, parse_multi_course_timetable, parse_timetable
    from services.cosmos_service import get_storage
    from config import Config
    import os
    import uuid
    from datetime import datetime

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "요청 데이터가 없습니다."}), 400

    filepath = data.get('filepath')
    selected_sheets = data.get('sheets', [])
    course_name = _sanitize_name(data.get('course_name', ''))
    color = data.get('color', '#4A90D9')
    start_time = data.get('start_time', '09:00')

    # 입력 검증
    if not filepath or not os.path.exists(filepath):
        return jsonify({"success": False, "error": "업로드된 파일을 찾을 수 없습니다."}), 400

    # Path Traversal 방지: filepath가 UPLOAD_FOLDER 내부인지 검증
    real_filepath = os.path.realpath(filepath)
    real_upload_folder = os.path.realpath(Config.UPLOAD_FOLDER)
    if not real_filepath.startswith(real_upload_folder + os.sep):
        logger.warning(f"Path Traversal 시도 감지: {filepath}")
        return jsonify({"success": False, "error": "잘못된 파일 경로입니다."}), 400

    try:
        timetable_format = detect_timetable_format(filepath)
    except Exception as error:
        logger.exception('시간표 형식 감지 실패: %s', filepath)
        return jsonify({"success": False, "error": "엑셀 파일을 읽을 수 없습니다."}), 400

    if timetable_format == 'multi_course':
        try:
            parsed_entries = parse_multi_course_timetable(filepath)
            entries_by_course = {}
            errors = []
            for entry in parsed_entries:
                row_number = entry.pop('_row_number')
                try:
                    location_fields = _resolve_location(entry)
                    link_fields = _resolve_class_links(entry, location_fields['location_type'])
                except ValueError as error:
                    errors.append(f'{row_number}행: {error}')
                    continue
                entry['instructor'] = _normalize_instructor(entry['instructor'])
                entry.update(location_fields)
                entry.update(link_fields)
                course_name_for_entry = entry.pop('course_name')
                entries_by_course.setdefault(course_name_for_entry, []).append(entry)

            if errors:
                shown_errors = errors[:20]
                remaining = len(errors) - len(shown_errors)
                suffix = f'\n그 외 {remaining}개 오류가 더 있습니다.' if remaining else ''
                return jsonify({
                    "success": False,
                    "error": '표 양식 오류:\n' + '\n'.join(shown_errors) + suffix,
                }), 400

            if not entries_by_course:
                return jsonify({"success": False, "error": "가져올 수업 일정이 없습니다."}), 400

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = os.path.basename(filepath).split('_', 1)[-1] if '_' in os.path.basename(filepath) else os.path.basename(filepath)
            storage = get_storage()
            course_ids = []
            total_entries = 0
            for index, (name, course_entries) in enumerate(entries_by_course.items()):
                course_id = f"course_{timestamp}_{str(uuid.uuid4())[:8]}"
                course = {
                    "id": course_id,
                    "type": "course",
                    "name": name,
                    "color": Config.COURSE_COLORS[index % len(Config.COURSE_COLORS)],
                    "file_name": file_name,
                    "uploaded_at": datetime.now().isoformat(),
                    "default_start_time": course_entries[0]['start_time'],
                    "entry_count": len(course_entries),
                }
                storage.save_course(course, course_entries)
                course_ids.append(course_id)
                total_entries += len(course_entries)

            try:
                os.remove(filepath)
            except OSError:
                pass

            message = f"{len(course_ids)}개 과정, {total_entries}개 수업 일정이 등록되었습니다."
            logger.info("표 시간표 등록 완료: %s", message)
            return jsonify({
                "success": True,
                "message": message,
                "course_ids": course_ids,
                "course_count": len(course_ids),
                "entry_count": total_entries,
            })
        except ValueError as error:
            return jsonify({"success": False, "error": str(error)}), 400
        except Exception:
            logger.exception('표 시간표 저장 실패: %s', filepath)
            return jsonify({"success": False, "error": "표 시간표 저장 중 오류가 발생했습니다."}), 500

    if not selected_sheets:
        return jsonify({"success": False, "error": "시트를 선택해주세요."}), 400
    if not course_name:
        return jsonify({"success": False, "error": "과정명을 입력해주세요."}), 400
    if len(course_name) < 2:
        return jsonify({"success": False, "error": "과정명은 2자 이상 입력해주세요."}), 400
    if not _validate_color(color):
        color = '#4A90D9'  # 유효하지 않으면 기본 색상
    if not _validate_time(start_time):
        start_time = '09:00'  # 유효하지 않으면 기본 시간

    try:
        entries = parse_timetable(filepath, selected_sheets, start_time)

        if not entries:
            return jsonify({"success": False, "error": "파싱된 수업 일정이 없습니다. 엑셀 형식을 확인해주세요."}), 400

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        course_id = f"course_{timestamp}_{unique_id}"

        course = {
            "id": course_id,
            "type": "course",
            "name": course_name,
            "color": color,
            "file_name": os.path.basename(filepath).split('_', 1)[-1] if '_' in os.path.basename(filepath) else os.path.basename(filepath),
            "uploaded_at": datetime.now().isoformat(),
            "default_start_time": start_time,
            "entry_count": len(entries)
        }

        storage = get_storage()
        storage.save_course(course, entries)

        # 임시 파일 삭제
        try:
            os.remove(filepath)
        except OSError:
            pass

        logger.info(f"과정 등록 완료: {course_name} ({len(entries)}개 일정)")
        return jsonify({
            "success": True,
            "message": f"'{course_name}' 과정이 등록되었습니다. ({len(entries)}개 수업 일정)",
            "course_id": course_id,
            "entry_count": len(entries)
        })
    except Exception as e:
        logger.error(f"파싱 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": "시간표 파싱 중 오류가 발생했습니다. 엑셀 형식을 확인해주세요."}), 400


@api_bp.route('/courses/quick', methods=['POST'])
def create_course_quick():
    """과정 빠른 생성 (엑셀 업로드 없이 이름과 색상만으로)"""
    from services.cosmos_service import get_storage
    import uuid
    from datetime import datetime

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "요청 데이터가 없습니다."}), 400

    course_name = _sanitize_name(data.get('course_name', ''))
    color = data.get('color', '#4A90D9')
    start_time = data.get('start_time', '09:00')

    if not course_name:
        return jsonify({"success": False, "error": "과정명을 입력해주세요."}), 400
    if len(course_name) < 2:
        return jsonify({"success": False, "error": "과정명은 2자 이상 입력해주세요."}), 400
    if not _validate_color(color):
        color = '#4A90D9'
    if not _validate_time(start_time):
        start_time = '09:00'

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    course_id = f"course_{timestamp}_{unique_id}"

    course = {
        "id": course_id,
        "type": "course",
        "name": course_name,
        "color": color,
        "file_name": "",
        "uploaded_at": datetime.now().isoformat(),
        "default_start_time": start_time,
        "entry_count": 0,
    }

    storage = get_storage()
    result_id = storage.create_course(course)
    if result_id:
        logger.info(f"과정 빠른 생성: {course_name}")
        return jsonify({
            "success": True,
            "message": f"'{course_name}' 과정이 생성되었습니다.",
            "course_id": result_id,
        })
    return jsonify({"success": False, "error": "과정 생성에 실패했습니다."}), 500


@api_bp.route('/courses/<course_id>', methods=['DELETE'])
def delete_course(course_id):
    """과정 삭제"""
    from services.cosmos_service import get_storage
    storage = get_storage()
    success = storage.delete_course(course_id)
    if success:
        try:
            from services.reminder_storage import get_reminder_storage
            get_reminder_storage().delete_course_assignments(course_id)
        except Exception:
            logger.exception('과정의 리마인드 설정 정리 실패: %s', course_id)
        logger.info(f"과정 삭제: {course_id}")
        return jsonify({"success": True, "message": "과정이 삭제되었습니다."})
    return jsonify({"success": False, "error": "과정을 찾을 수 없습니다."}), 404


@api_bp.route('/courses/<course_id>', methods=['PUT'])
def update_course(course_id):
    """과정 정보 수정 (이름, 색상, 시작시간)"""
    from services.cosmos_service import get_storage
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "요청 데이터가 없습니다."}), 400

    # 업데이트 필드 검증
    validated = {}
    if 'name' in data:
        name = _sanitize_name(data['name'])
        if len(name) < 2:
            return jsonify({"success": False, "error": "과정명은 2자 이상 입력해주세요."}), 400
        validated['name'] = name
    if 'color' in data:
        if not _validate_color(data['color']):
            return jsonify({"success": False, "error": "유효하지 않은 색상 형식입니다."}), 400
        validated['color'] = data['color']
    if 'default_start_time' in data:
        if not _validate_time(data['default_start_time']):
            return jsonify({"success": False, "error": "유효하지 않은 시간 형식입니다."}), 400
        validated['default_start_time'] = data['default_start_time']

    if not validated:
        return jsonify({"success": False, "error": "수정할 항목이 없습니다."}), 400

    storage = get_storage()
    success = storage.update_course(course_id, validated)
    if success:
        return jsonify({"success": True, "message": "과정 정보가 수정되었습니다."})
    return jsonify({"success": False, "error": "과정을 찾을 수 없습니다."}), 404


@api_bp.route('/courses/<course_id>/entries', methods=['POST'])
def add_entry(course_id):
    """과정에 개별 수업 일정 추가"""
    from services.cosmos_service import get_storage

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "요청 데이터가 없습니다."}), 400

    # 필수 필드
    date = data.get('date', '').strip()
    class_name = _sanitize_name(data.get('class_name', ''), max_len=None)

    # 선택 필드 (기본값)
    instructor = _normalize_instructor(data.get('instructor', ''))
    is_holiday = bool(data.get('is_holiday', False))

    # 입력 검증
    if not date or not DATE_RE.match(date):
        return jsonify({"success": False, "error": "날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)"}), 400
    if not class_name:
        return jsonify({"success": False, "error": "수업명을 입력해주세요."}), 400
    try:
        hours, start_time, end_time = _resolve_class_time(data)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        location_fields = _resolve_location(data)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        class_links = _resolve_class_links(data, location_fields['location_type'])
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    entry = {
        "date": date,
        "class_name": class_name,
        "instructor": instructor,
        "hours": hours,
        "start_time": start_time,
        "end_time": end_time,
        "is_holiday": is_holiday,
        **location_fields,
        **class_links,
    }

    storage = get_storage()
    entry_id = storage.add_entry(course_id, entry)
    if entry_id:
        logger.info(f"수업 일정 추가: {course_id} / {class_name} ({date})")
        return jsonify({
            "success": True,
            "message": f"'{class_name}' 수업이 추가되었습니다.",
            "entry_id": entry_id,
        })
    return jsonify({"success": False, "error": "과정을 찾을 수 없습니다."}), 404


@api_bp.route('/courses/<course_id>/entries/<entry_id>', methods=['DELETE'])
def delete_entry(course_id, entry_id):
    """개별 수업 일정 삭제"""
    from services.cosmos_service import get_storage
    storage = get_storage()
    success = storage.delete_entry(course_id, entry_id)
    if success:
        try:
            from services.reminder_storage import get_reminder_storage
            get_reminder_storage().delete_assignment(course_id, entry_id)
        except Exception:
            logger.exception('수업의 리마인드 설정 정리 실패: %s / %s', course_id, entry_id)
        logger.info(f"수업 일정 삭제: {course_id} / {entry_id}")
        return jsonify({"success": True, "message": "수업 일정이 삭제되었습니다."})
    return jsonify({"success": False, "error": "수업 일정을 찾을 수 없습니다."}), 404


@api_bp.route('/courses/<course_id>/entries/<entry_id>', methods=['PUT'])
def update_entry(course_id, entry_id):
    """개별 수업 일정 수정"""
    from services.cosmos_service import get_storage

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "요청 데이터가 없습니다."}), 400

    date = data.get('date', '').strip()
    class_name = _sanitize_name(data.get('class_name', ''), max_len=None)

    if not date or not DATE_RE.match(date):
        return jsonify({"success": False, "error": "날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)"}), 400
    if not class_name:
        return jsonify({"success": False, "error": "수업명을 입력해주세요."}), 400

    instructor = _normalize_instructor(data.get('instructor', ''))
    is_holiday = bool(data.get('is_holiday', False))
    try:
        hours, start_time, end_time = _resolve_class_time(data)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        location_fields = _resolve_location(data)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        class_links = _resolve_class_links(data, location_fields['location_type'])
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    updates = {
        "date": date,
        "class_name": class_name,
        "instructor": instructor,
        "hours": hours,
        "start_time": start_time,
        "end_time": end_time,
        "is_holiday": is_holiday,
        **location_fields,
        **class_links,
    }

    storage = get_storage()
    success = storage.update_entry(course_id, entry_id, updates)
    if success:
        if is_holiday:
            try:
                from services.reminder_storage import get_reminder_storage
                get_reminder_storage().delete_assignment(course_id, entry_id)
            except Exception:
                logger.exception('휴일의 리마인드 설정 정리 실패: %s / %s', course_id, entry_id)
        logger.info(f"수업 일정 수정: {course_id} / {entry_id} ({class_name})")
        return jsonify({"success": True, "message": f"'{class_name}' 수업이 수정되었습니다."})
    return jsonify({"success": False, "error": "수업 일정을 찾을 수 없습니다."}), 404
