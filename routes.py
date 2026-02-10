"""
Timetable Dashboard - 라우트 정의
"""
import re
import logging
from flask import Blueprint, render_template, jsonify, request

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
    return name.strip()[:max_len] if name else ''


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
    courses = storage.get_all_courses()
    # entries 제거 → 경량 응답
    course_list = []
    for c in courses:
        course_list.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "color": c.get("color"),
            "file_name": c.get("file_name"),
            "uploaded_at": c.get("uploaded_at"),
            "default_start_time": c.get("default_start_time"),
            "entry_count": c.get("entry_count", len(c.get("entries", []))),
        })
    return jsonify({"success": True, "courses": course_list})


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
    from services.excel_parser import get_sheet_names
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
    from werkzeug.utils import secure_filename as _secure
    original_name = _secure(file.filename) or 'upload.xlsx'
    safe_name = f"{_uuid.uuid4().hex[:8]}_{original_name}"
    filepath = os.path.join(Config.UPLOAD_FOLDER, safe_name)
    file.save(filepath)

    # 실제 엑셀 파일인지 검증
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True)
        wb.close()
    except Exception:
        try:
            os.remove(filepath)
        except OSError:
            pass
        return jsonify({"success": False, "error": "유효한 엑셀 파일이 아닙니다."}), 400

    try:
        sheets = get_sheet_names(filepath)
        if not sheets:
            os.remove(filepath)
            return jsonify({"success": False, "error": "유효한 시트를 찾을 수 없습니다."}), 400
        return jsonify({"success": True, "sheets": sheets, "filepath": filepath})
    except Exception as e:
        logger.error(f"엑셀 파일 읽기 실패: {e}", exc_info=True)
        try:
            os.remove(filepath)
        except OSError:
            pass
        return jsonify({"success": False, "error": "엑셀 파일을 읽을 수 없습니다. 파일 형식을 확인해주세요."}), 400


@api_bp.route('/upload', methods=['POST'])
def upload_course():
    """엑셀 파싱 후 과정 저장"""
    from services.excel_parser import parse_timetable
    from services.cosmos_service import get_storage
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
    from services.excel_parser import calculate_end_time

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "요청 데이터가 없습니다."}), 400

    # 필수 필드
    date = data.get('date', '').strip()
    class_name = _sanitize_name(data.get('class_name', ''), max_len=100)

    # 선택 필드 (기본값)
    instructor = _sanitize_name(data.get('instructor', ''), max_len=50)
    hours = data.get('hours', 8)
    start_time = data.get('start_time', '09:00')
    is_holiday = bool(data.get('is_holiday', False))

    # 입력 검증
    if not date or not DATE_RE.match(date):
        return jsonify({"success": False, "error": "날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)"}), 400
    if not class_name:
        return jsonify({"success": False, "error": "수업명을 입력해주세요."}), 400
    if not isinstance(hours, int) or hours < 1 or hours > 12:
        return jsonify({"success": False, "error": "수업시간은 1~12시간 사이로 입력해주세요."}), 400
    if not _validate_time(start_time):
        start_time = '09:00'

    # end_time 계산
    end_time = calculate_end_time(start_time, hours)

    entry = {
        "date": date,
        "class_name": class_name,
        "instructor": instructor,
        "hours": hours,
        "start_time": start_time,
        "end_time": end_time,
        "is_holiday": is_holiday,
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
        logger.info(f"수업 일정 삭제: {course_id} / {entry_id}")
        return jsonify({"success": True, "message": "수업 일정이 삭제되었습니다."})
    return jsonify({"success": False, "error": "수업 일정을 찾을 수 없습니다."}), 404
