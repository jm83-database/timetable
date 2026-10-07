"""
직원근무표 라우트 (페이지 + /api/roster)
"""
import os
import logging
from flask import Blueprint, render_template, jsonify, request

from config import Config
from routes import DATE_RE, _sanitize_name
from models import ROSTER_CATEGORIES
from utils.error_handlers import handle_errors

logger = logging.getLogger(__name__)

roster_bp = Blueprint('roster', __name__)
roster_api_bp = Blueprint('roster_api', __name__, url_prefix='/api/roster')


@roster_bp.route('/roster')
def roster_page():
    return render_template('roster.html')


def _parse_people(value):
    """리스트 또는 '김철수, 이영희' 문자열 → 이름 리스트"""
    if isinstance(value, str):
        value = value.replace('/', ',').split(',')
    if not isinstance(value, list):
        return []
    names = []
    for v in value:
        n = _sanitize_name(str(v), max_len=20)
        if n and n not in names:
            names.append(n)
    return names[:20]


def _validate_entry(data, partial=False):
    """요청 본문 → 저장용 dict. 오류 시 ValueError"""
    out = {}
    if 'date' in data or not partial:
        date = str(data.get('date', '')).strip()
        if not DATE_RE.match(date):
            raise ValueError("날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)")
        out['date'] = date
    if 'category' in data or not partial:
        cat = str(data.get('category', 'event')).strip()
        if cat not in ROSTER_CATEGORIES:
            raise ValueError("구분 값이 올바르지 않습니다.")
        out['category'] = cat
    if 'title' in data or not partial:
        out['title'] = _sanitize_name(str(data.get('title', '')), max_len=100)
    if 'people' in data or not partial:
        out['people'] = _parse_people(data.get('people', []))
    if 'note' in data or not partial:
        out['note'] = _sanitize_name(str(data.get('note', '')), max_len=300)
    if not partial:
        out['raw_text'] = ''
        out['source_sheet'] = 'manual'
        if not out['title'] and not out['people'] and not out['note']:
            raise ValueError("제목, 담당자, 메모 중 하나는 입력해야 합니다.")
    return out


@roster_api_bp.route('/entries', methods=['GET'])
@handle_errors
def list_entries():
    """FullCalendar 이벤트 (start/end는 FullCalendar가 보내는 ISO 문자열)"""
    from services.roster_storage import get_roster_storage
    from services.calendar_service import format_roster_events, build_employee_colors
    storage = get_roster_storage()
    start = (request.args.get('start') or '')[:10] or None
    end = (request.args.get('end') or '')[:10] or None
    # 색상은 전체 데이터 기준으로 고정해 월을 이동해도 직원 색이 바뀌지 않게 함
    colors = build_employee_colors(storage.get_entries())
    return jsonify(format_roster_events(storage.get_entries(start, end), colors))


@roster_api_bp.route('/employees', methods=['GET'])
@handle_errors
def list_employees():
    from services.roster_storage import get_roster_storage
    from services.calendar_service import build_employee_colors
    entries = get_roster_storage().get_entries()
    colors = build_employee_colors(entries)
    months = sorted({e.get('date', '')[:7] for e in entries if e.get('date')})
    return jsonify({
        "success": True,
        "employees": [{"name": n, "color": c} for n, c in colors.items()],
        "entry_count": len(entries),
        "months": months,
        "category_colors": Config.ROSTER_CATEGORY_COLORS,
    })


@roster_api_bp.route('/day', methods=['GET'])
@handle_errors
def day_summary():
    from services.roster_storage import get_roster_storage
    from services.calendar_service import get_roster_day_summary
    date = (request.args.get('date') or '').strip()
    if not DATE_RE.match(date):
        raise ValueError("날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)")
    entries = [e for e in get_roster_storage().get_entries(date, None) if e.get('date') == date]
    return jsonify({"success": True, **get_roster_day_summary(entries, date)})


@roster_api_bp.route('/sheets', methods=['POST'])
@handle_errors
def roster_sheets():
    """엑셀 업로드 → 시트별 연/월 정보 (파일 저장은 기존 /api/sheets 로직 재사용)"""
    from routes import get_sheets
    from services.roster_parser import get_roster_sheet_info
    resp = get_sheets()
    payload, status = (resp if isinstance(resp, tuple) else (resp, 200))
    if status != 200:
        return payload, status
    data = payload.get_json()
    data['sheets'] = get_roster_sheet_info(data['filepath'])
    return jsonify(data)


@roster_api_bp.route('/upload', methods=['POST'])
@handle_errors
def roster_upload():
    from services.roster_parser import parse_roster
    from services.roster_storage import get_roster_storage

    data = request.get_json() or {}
    filepath = data.get('filepath', '')
    sheets = data.get('sheets', [])

    if not filepath or not os.path.exists(filepath):
        return jsonify({"success": False, "error": "업로드된 파일을 찾을 수 없습니다."}), 400
    real_filepath = os.path.realpath(filepath)
    if not real_filepath.startswith(os.path.realpath(Config.UPLOAD_FOLDER) + os.sep):
        logger.warning(f"Path Traversal 시도 감지: {filepath}")
        return jsonify({"success": False, "error": "잘못된 파일 경로입니다."}), 400
    if not sheets:
        return jsonify({"success": False, "error": "시트를 선택해주세요."}), 400

    entries, months = parse_roster(filepath, sheets)
    if not entries:
        return jsonify({"success": False, "error": "파싱된 근무 항목이 없습니다. 엑셀 형식을 확인해주세요."}), 400

    base = os.path.basename(filepath)
    file_name = base.split('_', 1)[-1] if '_' in base else base
    removed = get_roster_storage().replace_months(entries, months, file_name)
    try:
        os.remove(filepath)
    except OSError:
        pass

    month_labels = [f"{y}년 {m}월" for y, m in months]
    return jsonify({
        "success": True,
        "message": f"{', '.join(month_labels)} 근무표를 등록했습니다. ({len(entries)}건, 기존 {removed}건 교체)",
        "entry_count": len(entries),
        "replaced": removed,
        "months": month_labels,
    })


@roster_api_bp.route('/entries', methods=['POST'])
@handle_errors
def create_entry():
    from services.roster_storage import get_roster_storage
    entry = _validate_entry(request.get_json() or {})
    entry_id = get_roster_storage().add_entry(entry)
    return jsonify({"success": True, "entry_id": entry_id, "message": "근무 항목이 추가되었습니다."})


@roster_api_bp.route('/entries/<entry_id>', methods=['PUT'])
@handle_errors
def update_entry(entry_id):
    from services.roster_storage import get_roster_storage
    updates = _validate_entry(request.get_json() or {}, partial=True)
    if not updates:
        raise ValueError("수정할 항목이 없습니다.")
    if get_roster_storage().update_entry(entry_id, updates):
        return jsonify({"success": True, "message": "근무 항목이 수정되었습니다."})
    return jsonify({"success": False, "error": "항목을 찾을 수 없습니다."}), 404


@roster_api_bp.route('/entries/<entry_id>', methods=['DELETE'])
@handle_errors
def remove_entry(entry_id):
    from services.roster_storage import get_roster_storage
    if get_roster_storage().delete_entry(entry_id):
        return jsonify({"success": True, "message": "근무 항목이 삭제되었습니다."})
    return jsonify({"success": False, "error": "항목을 찾을 수 없습니다."}), 404
