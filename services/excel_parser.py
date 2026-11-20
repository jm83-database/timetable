"""
Vertex42 캘린더 엑셀 템플릿 파서
"""
import logging
import re
from datetime import date, datetime, time
from io import BytesIO

import openpyxl

logger = logging.getLogger(__name__)

MULTI_COURSE_HEADERS = (
    '날짜', '과정명', '수업명', '강사명', '시작 시각', '종료 시각',
    '장소 구분', '장소', '강의자료 URL', '온라인 수업 URL',
)
MULTI_COURSE_REQUIRED_HEADERS = {
    '날짜', '과정명', '수업명', '시작 시각', '종료 시각', '장소 구분',
}
MULTI_COURSE_TEMPLATE_ROWS = 5000

# 건너뛸 시트 (정보 페이지)
INFO_SHEETS = {'정보', '정보 (2)', 'Sheet1', '작성안내'}

# 주 시작 행 (6행 간격)
WEEK_START_ROWS = [10, 16, 22, 28, 34, 40]

# 요일 설정: (날짜 열 인덱스, 수업명 열 인덱스)
# Mon=C(3)/D(4), Tue=E(5)/F(6), Wed=G(7)/H(8), Thu=I(9)/J(10), Fri=K(11)/M(13)
DAY_CONFIG = [
    (3, 4),    # Monday:   C=날짜, D=수업명
    (5, 6),    # Tuesday:  E=날짜, F=수업명
    (7, 8),    # Wednesday: G=날짜, H=수업명
    (9, 10),   # Thursday: I=날짜, J=수업명
    (11, 13),  # Friday:   K=날짜, M=수업명
]

# 공휴일/비수업 키워드
HOLIDAY_KEYWORDS = {
    '추석', '개천절', '한글날', '대체휴일', '방학', '어린이날',
    '현충일', '광복절', '석가탄신일', '삼일절', '신정', '성탄절',
    '구정', '설날', '연휴', '휴일', '메모', '새해',
}

# 점심시간 (분 단위)
LUNCH_START = 13 * 60
LUNCH_END = 14 * 60

# '?' 뒤 텍스트는 수업장소 (전각 '？' 포함). 장소가 없으면 온라인
LOCATION_MARK_RE = re.compile(r'[?？]')
ONLINE_LABEL = '온라인'


def get_sheet_names(filepath):
    """엑셀 파일의 시트 목록 반환 (정보 시트 제외)"""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    sheets = [name for name in wb.sheetnames if name not in INFO_SHEETS]
    wb.close()
    return sheets


def _load_workbook(filepath, **kwargs):
    with open(filepath, 'rb') as source:
        workbook_data = BytesIO(source.read())
    return openpyxl.load_workbook(workbook_data, **kwargs)


def detect_timetable_format(filepath):
    """첫 번째 시트의 헤더로 표 형식 시간표인지 구분한다."""
    wb = _load_workbook(filepath, data_only=True)
    try:
        if not wb.worksheets:
            return 'vertex42'
        header_row = next(wb.worksheets[0].iter_rows(
            min_row=1, max_row=1, values_only=True
        ), ())
        headers = {str(value).strip() for value in header_row if value is not None}
        if (wb.worksheets[0].title == '수업목록'
                or MULTI_COURSE_REQUIRED_HEADERS.issubset(headers)
                or '과정명' in headers):
            return 'multi_course'
        return 'vertex42'
    finally:
        wb.close()


def _table_text(value, label):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValueError(f'{label}은 텍스트로 입력해주세요.')
    return value.strip()


def _table_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        value = value.strip()
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('날짜를 YYYY-MM-DD 형식으로 입력해주세요.')
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as error:
            raise ValueError('날짜를 YYYY-MM-DD 형식으로 입력해주세요.') from error
    raise ValueError('날짜를 YYYY-MM-DD 형식으로 입력해주세요.')


def _table_time(value, label):
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        return value.strftime('%H:%M')
    if isinstance(value, str):
        match = re.fullmatch(r'(\d{1,2}):([0-5]\d)', value.strip())
        if match and int(match.group(1)) < 24:
            return f'{int(match.group(1)):02d}:{match.group(2)}'
    raise ValueError(f'{label}을 HH:MM 형식으로 입력해주세요.')


def parse_multi_course_timetable(filepath):
    """한 행을 한 수업으로 표현한 다중 과정 시간표를 파싱한다."""
    wb = _load_workbook(filepath, data_only=True)
    try:
        if not wb.worksheets:
            raise ValueError('수업목록 시트를 찾을 수 없습니다.')
        ws = wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        header_row = next(rows, None)
        headers = {
            str(value).strip(): index
            for index, value in enumerate(header_row or ())
            if value is not None
        }
        missing = MULTI_COURSE_REQUIRED_HEADERS - headers.keys()
        if missing:
            raise ValueError(f"필수 열이 없습니다: {', '.join(sorted(missing))}")

        entries = []
        errors = []
        for row_number, values in enumerate(rows, start=2):
            if not any(value is not None and str(value).strip() for value in values):
                continue
            row = {
                header: values[index] if index < len(values) else None
                for header, index in headers.items()
            }
            try:
                date_value = _table_date(row.get('날짜'))
                course_name = _table_text(row.get('과정명'), '과정명')
                class_name = _table_text(row.get('수업명'), '수업명')
                if len(course_name) < 2:
                    raise ValueError('과정명은 2자 이상 입력해주세요.')
                if len(course_name) > 50:
                    raise ValueError('과정명은 50자 이하로 입력해주세요.')
                if not class_name:
                    raise ValueError('수업명을 입력해주세요.')

                start_time = _table_time(row.get('시작 시각'), '시작 시각')
                end_time = _table_time(row.get('종료 시각'), '종료 시각')
                hours = calculate_hours(start_time, end_time)
                if hours is None or not 0 < hours <= 12:
                    raise ValueError('수업 시간은 시작보다 늦고 12시간 이내여야 합니다.')

                location_type = _table_text(row.get('장소 구분'), '장소 구분').lower()
                if location_type in ('', '온라인', 'online'):
                    location_type = 'online'
                elif location_type in ('오프라인', 'offline'):
                    location_type = 'offline'
                else:
                    raise ValueError('장소 구분은 온라인 또는 오프라인으로 입력해주세요.')
                location = _table_text(row.get('장소'), '장소')
                if location_type == 'offline' and not location:
                    raise ValueError('오프라인 수업은 장소를 입력해주세요.')
                if location_type == 'online':
                    location = ''

                entries.append({
                    'date': date_value,
                    'course_name': course_name,
                    'class_name': class_name,
                    'instructor': _table_text(row.get('강사명'), '강사명'),
                    'hours': hours,
                    'start_time': start_time,
                    'end_time': end_time,
                    'location_type': location_type,
                    'location': location,
                    'course_material_url': _table_text(row.get('강의자료 URL'), '강의자료 URL'),
                    'online_class_url': _table_text(row.get('온라인 수업 URL'), '온라인 수업 URL'),
                    '_row_number': row_number,
                })
            except (ValueError, TypeError) as error:
                errors.append(f'{row_number}행: {error}')

        if errors:
            shown_errors = errors[:20]
            remaining = len(errors) - len(shown_errors)
            suffix = f'\n그 외 {remaining}개 오류가 더 있습니다.' if remaining else ''
            raise ValueError('표 양식 오류:\n' + '\n'.join(shown_errors) + suffix)
        if not entries:
            raise ValueError('가져올 수업 일정이 없습니다.')
        return entries
    finally:
        wb.close()


def create_multi_course_template():
    """다중 과정 시간표 입력용 Excel 템플릿을 생성한다."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = '수업목록'
    sheet.append(MULTI_COURSE_HEADERS)
    sheet.freeze_panes = 'A2'
    last_row = MULTI_COURSE_TEMPLATE_ROWS + 1
    sheet.auto_filter.ref = f'A1:J{last_row}'
    sheet.row_dimensions[1].height = 28
    widths = (14, 24, 32, 20, 14, 14, 14, 30, 42, 42)
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[openpyxl.utils.get_column_letter(column)].width = width
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1F4E78')
        cell.alignment = Alignment(horizontal='center', vertical='center')
    for row_number in range(2, last_row + 1):
        sheet.cell(row_number, 1).number_format = 'yyyy-mm-dd'
        sheet.cell(row_number, 5).number_format = 'hh:mm'
        sheet.cell(row_number, 6).number_format = 'hh:mm'
    location_validation = DataValidation(type='list', formula1='"온라인,오프라인"', allow_blank=True)
    sheet.add_data_validation(location_validation)
    location_validation.add(f'G2:G{last_row}')

    guide = workbook.create_sheet('작성안내')
    instructions = (
        ('다중 과정 시간표 작성 안내',),
        ('수업목록 시트에서 1행의 제목은 변경하지 말고, 2행부터 한 행에 수업 하나를 입력하세요.',),
        ('같은 날짜와 같은 시간에 여러 과정이 운영되면 과정별로 행을 추가하세요.',),
        ('과정별 색상은 등록 순서대로 앱에서 자동 지정합니다.',),
        ('날짜는 YYYY-MM-DD, 시작·종료 시각은 HH:MM 형식으로 입력하세요.',),
        ('과정명, 수업명, 날짜, 시작 시각, 종료 시각, 장소 구분은 필수입니다.',),
        ('장소 구분은 온라인 또는 오프라인으로 입력하세요. 비워두면 온라인으로 처리하며, 오프라인은 장소를 입력하세요.',),
        ('강사명, 강의자료 URL, 온라인 수업 URL은 선택 항목입니다. URL은 http:// 또는 https://로 시작해야 합니다.',),
        ('온라인 수업 URL은 온라인 일정에만 저장됩니다.',),
        ('예시',),
        ('2026-11-20', 'AI 과정 A', 'AI 기초', '홍길동', '09:00', '12:00', '온라인', '', 'https://padlet.com/example', 'https://zoom.us/j/example'),
        ('2026-11-20', '데이터 과정 B', '데이터 분석', '김강사', '09:00', '18:00', '오프라인', '서울 교육장', '', ''),
    )
    for row in instructions:
        guide.append(row)
    guide.column_dimensions['A'].width = 110
    guide.column_dimensions['B'].width = 24
    for column in range(3, 11):
        guide.column_dimensions[openpyxl.utils.get_column_letter(column)].width = 22
    guide['A1'].font = Font(bold=True, size=14, color='1F4E78')
    guide.freeze_panes = 'A2'

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def _to_minutes(time_str):
    h, m = map(int, time_str.split(':'))
    return h * 60 + m


def _split_location(text):
    if not isinstance(text, str):
        return text, None
    match = LOCATION_MARK_RE.search(text)
    if not match:
        return text.strip(), None
    return text[:match.start()].strip(), text[match.end():].strip()


def _find_location(ws, date_col, class_col, week_row):
    for offset in range(0, 6):
        for col in sorted({date_col, class_col}):
            value = ws.cell(row=week_row + offset, column=col).value
            if isinstance(value, str):
                _, location = _split_location(value)
                if location is not None:
                    return location
    return None


def _location_fields(location):
    if not location or location == ONLINE_LABEL:
        return {'location_type': 'online', 'location': ''}
    return {'location_type': 'offline', 'location': location}


def normalize_hours(value):
    """수업시간을 분 단위로 반올림 (정수면 int, 예: 4.5 / 4.333..). 숫자가 아니면 None"""
    if isinstance(value, bool):
        return None
    try:
        minutes = round(float(value) * 60)
    except (TypeError, ValueError, OverflowError):
        return None
    hours = minutes / 60
    return int(hours) if hours.is_integer() else hours


def calculate_end_time(start_time_str, hours):
    """시작 시간 + 수업 시간(분 단위 소수 허용) → 종료 시간 계산 (점심시간 13:00~14:00 포함)"""
    start = _to_minutes(start_time_str)
    end = start + round(hours * 60)

    # 점심시간 (13:00~14:00) 걸치면 1시간 추가
    if start < LUNCH_START and end > LUNCH_START:
        end += 60

    return f"{(end // 60) % 24:02d}:{end % 60:02d}"


def calculate_hours(start_time_str, end_time_str):
    """시작~종료 시각 → 수업시간 (13:00 이전 시작 시 점심시간과 겹치는 분만큼 제외). 종료가 시작 이전이면 None"""
    start = _to_minutes(start_time_str)
    end = _to_minutes(end_time_str)
    if end <= start:
        return None
    minutes = end - start
    if start < LUNCH_START:
        minutes -= max(0, min(end, LUNCH_END) - LUNCH_START)
    return normalize_hours(minutes / 60)


def _detect_week_start_rows(ws):
    """시트에서 실제 주 시작 행을 동적으로 감지"""
    date_rows = set()
    for row in range(8, 55):
        for date_col, _ in DAY_CONFIG:
            cell_val = ws.cell(row=row, column=date_col).value
            if isinstance(cell_val, datetime) and cell_val.year >= 2020:
                date_rows.add(row)
                break

    if not date_rows:
        logger.warning("날짜 행을 감지하지 못했습니다. 기본값 사용.")
        return WEEK_START_ROWS  # fallback

    # 인접 행 그룹핑: 4행 이상 떨어져 있으면 새로운 주
    sorted_rows = sorted(date_rows)
    week_rows = [sorted_rows[0]]
    for r in sorted_rows[1:]:
        if r - week_rows[-1] >= 4:
            week_rows.append(r)

    logger.info(f"감지된 주 시작 행: {week_rows}")
    return week_rows


NOT_NAME_WORDS = {
    '발표', '자격증', '주제별', '네트워킹', '온라인', '오프라인',
    '자기소개', '팀구성', '특강', '보강', '실습', '복습',
    '평가', '시험', '면접', '상담', '수료', '졸업',
    '쇼츠', '영상', '촬영', '편집', '기획', '운영',
}


def _is_korean_name(text):
    """한국어 강사 이름인지 판별 (2~4자 한글, 설명 단어 제외)"""
    if not text or not isinstance(text, str):
        return False
    cleaned = text.strip()
    if not cleaned:
        return False
    # 숫자만 있는 경우 제외
    if cleaned.replace('h', '').replace('H', '').replace(' ', '').isdigit():
        return False
    # '8h', '4.5h' 같은 시간 형식 제외
    if re.match(r'^\d+(?:\.\d+)?h?$', cleaned, re.IGNORECASE):
        return False
    # 이름이 아닌 키워드 필터
    if cleaned in NOT_NAME_WORDS:
        return False
    # 한국어 이름: 2~4자 한글만 (한국 이름은 대부분 2~4자)
    if re.match(r'^[가-힣]{2,4}$', cleaned):
        return True
    # "황소영/정종현" 같은 복수 강사
    if re.match(r'^[가-힣]{2,4}/[가-힣]{2,4}$', cleaned):
        return True
    # "박정일강사" 같은 패턴 → "박정일"로 정제
    if re.match(r'^[가-힣]{2,4}강사$', cleaned):
        return True
    return False


def _extract_names_from_text(text):
    """텍스트에서 한국어 강사명 추출 (복수 가능)"""
    names = []

    # "황소영/정종현" 슬래시 구분
    if '/' in text:
        for part in text.split('/'):
            part = part.strip()
            if part.endswith('강사'):
                part = part[:-2]
            if re.match(r'^[가-힣]{2,4}$', part):
                names.append(part)
        if names:
            return names

    # "강명호,인선미" 쉼표 구분
    if ',' in text:
        for part in text.split(','):
            part = part.strip().split()[0] if part.strip() else ''
            if part.endswith('강사'):
                part = part[:-2]
            if re.match(r'^[가-힣]{2,4}$', part):
                names.append(part)
        if names:
            return names

    # 단어별 스캔
    for part in text.split():
        cleaned = part.strip()
        if cleaned.endswith('강사'):
            cleaned = cleaned[:-2]
        if cleaned in NOT_NAME_WORDS:
            continue
        if re.match(r'^[가-힣]{2,4}$', cleaned):
            names.append(cleaned)

    return names


def _extract_instructors_and_hours(ws, date_col, class_col, week_row, default_hours):
    """수업명 아래에서 강사명(복수)과 수업시간 추출"""
    instructors = []
    numeric_hours = None      # 숫자 셀에서 발견된 시간 (우선순위 1)
    text_hours_list = []      # 텍스트 "Xh"에서 발견된 시간들

    # 날짜 열과 수업명 열 모두에서 스캔
    scan_cols = sorted(set([date_col, class_col]))

    for offset in range(1, 6):
        row = week_row + offset
        for col in scan_cols:
            cell_val = ws.cell(row=row, column=col).value
            if cell_val is None:
                continue

            if isinstance(cell_val, (int, float)):
                # 숫자: 수업시간 (0 초과 ~12 범위, 소수 허용)
                val = float(cell_val)
                if 0 < val <= 12 and numeric_hours is None:
                    numeric_hours = normalize_hours(val)
            elif isinstance(cell_val, str):
                text = _split_location(cell_val)[0]
                if not text:
                    continue

                # 강사명 추출 (복수 수집)
                names = _extract_names_from_text(text)
                for name in names:
                    if name not in instructors:
                        instructors.append(name)

                # 텍스트 내 시간 추출 (12h 이하만 — 16h 버그 수정, '4.5h' 소수 허용)
                for part in text.split():
                    m = re.match(r'^(\d+(?:\.\d+)?)h$', part, re.IGNORECASE)
                    if m:
                        h = float(m.group(1))
                        if 0 < h <= 12:
                            text_hours_list.append(h)

    # 시간 결정: 숫자 셀 우선 → 텍스트 합산 → 기본값
    if numeric_hours is not None:
        hours = numeric_hours
    elif text_hours_list:
        hours = normalize_hours(sum(text_hours_list))
    else:
        hours = default_hours

    # 강사 있고 시간 없으면 기본값
    if instructors and numeric_hours is None and not text_hours_list:
        logger.debug(f"  강사 {instructors} 발견, 시간 미지정 → 기본 {hours}h 적용")

    instructor_str = ",".join(instructors)
    return instructor_str, hours


def parse_timetable(filepath, selected_sheets, default_start_time='09:00', default_hours=8):
    """엑셀 시간표 파싱 → ClassEntry 리스트 반환"""
    wb = _load_workbook(filepath, data_only=True)
    entries = []

    for sheet_name in selected_sheets:
        if sheet_name in INFO_SHEETS:
            continue
        if sheet_name not in wb.sheetnames:
            logger.warning(f"시트 '{sheet_name}'을 찾을 수 없습니다.")
            continue

        ws = wb[sheet_name]
        logger.info(f"시트 '{sheet_name}' 파싱 중...")

        # 동적으로 주 시작 행 감지
        week_start_rows = _detect_week_start_rows(ws)

        for week_row in week_start_rows:
            for date_col, class_col in DAY_CONFIG:
                # 1. 날짜 읽기
                date_cell = ws.cell(row=week_row, column=date_col).value
                if date_cell is None:
                    continue
                if not isinstance(date_cell, datetime):
                    continue
                if date_cell.year < 2020:
                    continue

                # 2. 수업명 읽기
                class_cell = ws.cell(row=week_row, column=class_col).value
                if class_cell is None or not isinstance(class_cell, str):
                    continue
                class_name = _split_location(class_cell)[0].replace('\n', ' ').replace('\t', ' ')
                class_name = re.sub(r'\s+', ' ', class_name)
                if not class_name:
                    continue

                # 3. 공휴일 체크
                is_holiday = any(kw in class_name for kw in HOLIDAY_KEYWORDS)

                # 4. 수업명에서 잔여 시간 패턴 제거 ("수업명 3h" / "수업명 4.5h" → "수업명")
                class_name = re.sub(r'\s+\d+(?:\.\d+)?h\s*$', '', class_name, flags=re.IGNORECASE)

                # 5. 강사명(복수), 수업시간 추출
                instructor = ""
                hours = default_hours
                if not is_holiday:
                    instructor, hours = _extract_instructors_and_hours(
                        ws, date_col, class_col, week_row, default_hours
                    )

                # 6. 종료 시간 계산
                end_time = calculate_end_time(default_start_time, hours)

                # 7. Entry 생성
                entry = {
                    "date": date_cell.strftime('%Y-%m-%d'),
                    "class_name": class_name,
                    "instructor": instructor,
                    "hours": hours,
                    "start_time": default_start_time,
                    "end_time": end_time,
                    "is_holiday": is_holiday,
                    **_location_fields(_find_location(ws, date_col, class_col, week_row)),
                }
                entries.append(entry)
                logger.debug(f"  {entry['date']} | {class_name} | {instructor} | {hours}h")

    wb.close()
    logger.info(f"총 {len(entries)}개 수업 일정 파싱 완료")
    return entries
