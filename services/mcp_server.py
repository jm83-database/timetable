"""MCP tools and the Streamable HTTP endpoint for timetable data."""
import logging
import re
from contextlib import asynccontextmanager
from datetime import date as Date, timedelta
from typing import Literal
from urllib.parse import urlsplit

from a2wsgi import WSGIMiddleware
from jwt.exceptions import PyJWKClientConnectionError
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount

from config import Config
from services.auth_service import validate_mcp_agent_token

logger = logging.getLogger(__name__)

_origin = Config.APP_ORIGIN
_host = urlsplit(_origin).netloc if _origin else ''
_allowed_hosts = [_host, f'{_host}:*'] if _host else [
    'localhost', 'localhost:*', '127.0.0.1', '127.0.0.1:*', 'testserver',
]
mcp = FastMCP(
    'Timetable',
    stateless_http=True,
    streamable_http_path='/',
    transport_security=TransportSecuritySettings(
        allowed_hosts=_allowed_hosts,
        allowed_origins=[_origin] if _origin else [],
    ),
)
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
MAX_RESULTS = 100


def _validated_date(value, label):
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise ValueError(f'{label} 형식은 YYYY-MM-DD여야 합니다.')
    try:
        return Date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f'{label}은 유효한 날짜여야 합니다.') from error


def _validated_date_range(start_value, end_value):
    start = _validated_date(start_value, 'start_date')
    end = _validated_date(end_value, 'end_date')
    if end < start:
        raise ValueError('end_date는 start_date보다 빠를 수 없습니다.')
    if end - start > timedelta(days=365):
        raise ValueError('날짜 범위는 최대 366일이어야 합니다.')
    return start, end


def _validate_limit(limit):
    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f'limit은 1에서 {MAX_RESULTS} 사이여야 합니다.')


def _course_summaries():
    from services.cosmos_service import get_storage

    fields = ('id', 'name', 'color', 'entry_count', 'default_start_time')
    return [
        {field: course.get(field) for field in fields}
        for course in get_storage().get_course_summaries()
    ]


@mcp.tool()
def list_courses() -> list[dict]:
    """List course names and IDs without returning their class schedules."""
    return _course_summaries()


@mcp.tool()
def search_classes(
    query: str | None = None,
    course_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
) -> dict:
    """Search classes by text, course, or inclusive date range; returns at most 100 compact rows."""
    _validate_limit(limit)
    if not any((query and query.strip(), course_id, start_date, end_date)):
        raise ValueError('query, course_id 또는 날짜 범위 중 하나 이상을 지정해주세요.')
    if bool(start_date) != bool(end_date):
        raise ValueError('start_date와 end_date를 함께 지정해주세요.')

    start, end = _validated_date_range(start_date, end_date) if start_date else (None, None)

    normalized_query = (query or '').strip().casefold()
    if len(normalized_query) > 100:
        raise ValueError('query는 100자 이하여야 합니다.')

    from services.cosmos_service import get_storage

    matches = []
    for course in get_storage().get_all_courses():
        if course_id and course.get('id') != course_id:
            continue
        for entry in course.get('entries', []):
            entry_date = entry.get('date', '')
            if start and not (start.isoformat() <= entry_date <= end.isoformat()):
                continue
            searchable = ' '.join((
                course.get('name', ''),
                entry.get('class_name', ''),
                entry.get('instructor', ''),
            )).casefold()
            if normalized_query and normalized_query not in searchable:
                continue
            matches.append({
                'course_id': course.get('id', ''),
                'course_name': course.get('name', ''),
                'entry_id': entry.get('id', ''),
                'date': entry_date,
                'class_name': entry.get('class_name', ''),
                'instructor': entry.get('instructor', ''),
                'start_time': entry.get('start_time', ''),
                'end_time': entry.get('end_time', ''),
                'hours': entry.get('hours', 0),
                'is_holiday': bool(entry.get('is_holiday', False)),
                'location_type': entry.get('location_type', ''),
                'location': entry.get('location', ''),
            })

    matches.sort(key=lambda row: (row['date'], row['start_time'], row['course_name'], row['entry_id']))
    return {'total_matches': len(matches), 'returned': min(len(matches), limit),
            'truncated': len(matches) > limit, 'entries': matches[:limit]}


@mcp.tool()
def list_roster_entries(
    start_date: str,
    end_date: str,
    category: str | None = None,
    employee: str | None = None,
    limit: int = 50,
) -> dict:
    """List compact employee roster entries in an inclusive date range (maximum 366 days)."""
    _validate_limit(limit)
    start, end = _validated_date_range(start_date, end_date)

    from services.roster_storage import get_roster_storage

    entries = get_roster_storage().get_entries(start.isoformat(), (end + timedelta(days=1)).isoformat())
    if category and category not in ('office', 'laptop', 'event', 'leave', 'memo'):
        raise ValueError('category는 office, laptop, event, leave, memo 중 하나여야 합니다.')
    normalized_employee = (employee or '').strip().casefold()
    rows = [
        {
            'id': entry.get('id', ''),
            'date': entry.get('date', ''),
            'category': entry.get('category', ''),
            'title': entry.get('title', ''),
            'people': entry.get('people', []),
            'note': entry.get('note', ''),
        }
        for entry in entries
        if (not category or entry.get('category') == category)
        and (not normalized_employee or any(
            normalized_employee in str(person).casefold() for person in entry.get('people', [])
        ))
    ]
    return {'total_matches': len(rows), 'returned': min(len(rows), limit),
            'truncated': len(rows) > limit, 'entries': rows[:limit]}


def _class_fields(data):
    from routes import (
        DATE_RE as API_DATE_RE,
        _normalize_instructor,
        _resolve_class_links,
        _resolve_class_time,
        _resolve_location,
        _sanitize_name,
        _validate_time,
    )

    date_value = data.get('date', '')
    _validated_date(date_value, 'date')
    if not API_DATE_RE.fullmatch(date_value):
        raise ValueError('날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)')
    if data.get('start_time') and not _validate_time(data['start_time']):
        raise ValueError('시작 시각 형식이 올바르지 않습니다. (HH:MM)')
    class_name = _sanitize_name(data.get('class_name', ''), max_len=None)
    if not class_name:
        raise ValueError('수업명을 입력해주세요.')
    hours, start_time, end_time = _resolve_class_time(data)
    location_fields = _resolve_location(data)
    return {
        'date': date_value,
        'class_name': class_name,
        'instructor': _normalize_instructor(data.get('instructor', '')),
        'hours': hours,
        'start_time': start_time,
        'end_time': end_time,
        'is_holiday': bool(data.get('is_holiday', False)),
        **location_fields,
        **_resolve_class_links(data, location_fields['location_type']),
    }


@mcp.tool()
def create_course(name: str, color: str = '#4A90D9', default_start_time: str = '09:00') -> dict:
    """Create an empty course that can receive new class entries."""
    from datetime import datetime
    import uuid

    from routes import _sanitize_name, _validate_color, _validate_time
    from services.cosmos_service import get_storage

    course_name = _sanitize_name(name)
    if len(course_name) < 2:
        raise ValueError('과정명은 2자 이상 입력해주세요.')
    if not _validate_color(color):
        raise ValueError('유효하지 않은 색상 형식입니다.')
    if not _validate_time(default_start_time):
        raise ValueError('유효하지 않은 시작 시각입니다. (HH:MM)')
    course = {
        'id': f"course_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}",
        'type': 'course',
        'name': course_name,
        'color': color,
        'file_name': '',
        'uploaded_at': datetime.now().isoformat(),
        'default_start_time': default_start_time,
        'entry_count': 0,
    }
    course_id = get_storage().create_course(course)
    if not course_id:
        raise RuntimeError('과정 생성에 실패했습니다.')
    return {'course_id': course_id, 'name': course_name}


@mcp.tool()
def create_class(
    course_id: str,
    date: str,
    class_name: str,
    location_type: Literal['online', 'offline'],
    instructor: str = '',
    hours: float = 8,
    start_time: str = '09:00',
    end_time: str | None = None,
    is_holiday: bool = False,
    location: str = '',
    course_material_url: str = '',
    online_class_url: str = '',
) -> dict:
    """Add one class. Explicitly choose online/offline; offline classes require a physical venue."""
    from services.cosmos_service import get_storage

    entry = _class_fields(locals())
    entry_id = get_storage().add_entry(course_id, entry)
    if not entry_id:
        raise ValueError('과정을 찾을 수 없습니다.')
    return {'course_id': course_id, 'entry_id': entry_id, 'date': entry['date'],
            'class_name': entry['class_name'], 'location_type': entry['location_type'],
            'location': entry['location']}


@mcp.tool()
def configure_class_reminders(
    course_id: str,
    entry_id: str,
    education_type: Literal['regular', 'short_term'] | None = None,
) -> dict:
    """Match this class's instructor names exactly to registered reminder contacts and assign matches.

    Call after creating a class. Unmatched instructors are reported and not added as recipients.
    Contact email addresses are never returned.
    """
    from services.cosmos_service import get_storage
    from services.reminder_storage import get_reminder_storage

    course = next(
        (item for item in get_storage().get_all_courses() if item.get('id') == course_id),
        None,
    )
    if not course:
        raise ValueError('과정을 찾을 수 없습니다.')
    entry = next(
        (item for item in course.get('entries', []) if item.get('id') == entry_id),
        None,
    )
    if not entry or entry.get('is_holiday'):
        raise ValueError('일반 수업 일정을 찾을 수 없습니다.')

    from services.reminder_storage import configure_assignment_for_instructors
    return configure_assignment_for_instructors(
        get_reminder_storage(),
        course_id,
        entry_id,
        entry.get('instructor', ''),
        education_type,
    )


@mcp.tool()
def update_class(
    course_id: str,
    entry_id: str,
    date: str | None = None,
    class_name: str | None = None,
    instructor: str | None = None,
    hours: float | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    is_holiday: bool | None = None,
    location_type: str | None = None,
    location: str | None = None,
    course_material_url: str | None = None,
    online_class_url: str | None = None,
) -> dict:
    """Update only supplied fields on one class; inspect the class first when changing time."""
    from services.cosmos_service import get_storage

    storage = get_storage()
    course = next((item for item in storage.get_all_courses() if item.get('id') == course_id), None)
    if not course:
        raise ValueError('과정을 찾을 수 없습니다.')
    existing = next((item for item in course.get('entries', []) if item.get('id') == entry_id), None)
    if not existing:
        raise ValueError('수업 일정을 찾을 수 없습니다.')

    supplied = {
        'date': date,
        'class_name': class_name,
        'instructor': instructor,
        'is_holiday': is_holiday,
        'location_type': location_type,
        'location': location,
        'course_material_url': course_material_url,
        'online_class_url': online_class_url,
    }
    if not any(value is not None for value in supplied.values()) and all(
        value is None for value in (hours, start_time, end_time)
    ):
        raise ValueError('수정할 항목이 없습니다.')

    merged = {**existing, **{key: value for key, value in supplied.items() if value is not None}}
    if end_time is not None:
        merged['start_time'] = start_time if start_time is not None else existing.get('start_time', '09:00')
        merged['end_time'] = end_time
    else:
        merged.pop('end_time', None)
        merged['start_time'] = start_time if start_time is not None else existing.get('start_time', '09:00')
        merged['hours'] = hours if hours is not None else existing.get('hours', 8)

    updates = _class_fields(merged)
    if not storage.update_entry(course_id, entry_id, updates):
        raise RuntimeError('수업 일정 수정에 실패했습니다.')
    return {'course_id': course_id, 'entry_id': entry_id, 'date': updates['date'],
            'class_name': updates['class_name']}


@mcp.tool()
def delete_class(course_id: str, entry_id: str) -> dict:
    """Delete one class and its reminder assignment."""
    from services.cosmos_service import get_storage

    if not get_storage().delete_entry(course_id, entry_id):
        raise ValueError('수업 일정을 찾을 수 없습니다.')
    from services.reminder_storage import get_reminder_storage
    get_reminder_storage().delete_assignment(course_id, entry_id)
    return {'course_id': course_id, 'entry_id': entry_id, 'deleted': True}


@mcp.tool()
def create_roster_entry(
    date: str,
    category: str,
    title: str = '',
    people: list[str] | str | None = None,
    note: str = '',
) -> dict:
    """Add one validated employee roster entry."""
    from routes_roster import _validate_entry
    from services.roster_storage import get_roster_storage

    entry = _validate_entry({'date': date, 'category': category, 'title': title,
                             'people': people or [], 'note': note})
    entry_id = get_roster_storage().add_entry(entry)
    return {'entry_id': entry_id, 'date': entry['date'], 'category': entry['category']}


@mcp.tool()
def update_roster_entry(
    entry_id: str,
    date: str | None = None,
    category: str | None = None,
    title: str | None = None,
    people: list[str] | str | None = None,
    note: str | None = None,
) -> dict:
    """Update only supplied fields on one employee roster entry."""
    from routes_roster import _validate_entry
    from services.roster_storage import get_roster_storage

    supplied = {'date': date, 'category': category, 'title': title, 'people': people, 'note': note}
    updates = {key: value for key, value in supplied.items() if value is not None}
    if not updates:
        raise ValueError('수정할 항목이 없습니다.')
    validated = _validate_entry(updates, partial=True)
    if not get_roster_storage().update_entry(entry_id, validated):
        raise ValueError('근무 항목을 찾을 수 없습니다.')
    return {'entry_id': entry_id, 'updated': True}


@mcp.tool()
def delete_roster_entry(entry_id: str) -> dict:
    """Delete one employee roster entry."""
    from services.roster_storage import get_roster_storage

    if not get_roster_storage().delete_entry(entry_id):
        raise ValueError('근무 항목을 찾을 수 없습니다.')
    return {'entry_id': entry_id, 'deleted': True}


class McpAuthMiddleware:
    def __init__(self, app, config, extensions):
        self.app = app
        self.config = config
        self.extensions = extensions

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        mode = self.config.get('AUTH_MODE')
        if mode == 'local' and not self.config.get('WEBSITE_SITE_NAME'):
            await self.app(scope, receive, send)
            return
        if mode != 'entra':
            response = JSONResponse({'error': 'MCP 인증을 사용할 수 없습니다.'}, status_code=503)
            await response(scope, receive, send)
            return

        headers = {name.lower(): value.decode('latin-1') for name, value in scope['headers']}
        authorization = headers.get(b'authorization', '')
        if authorization:
            scheme, _, token = authorization.partition(' ')
            if scheme.lower() != 'bearer' or not token or ' ' in token:
                token = ''
        else:
            token = headers.get(b'x-ms-token-aad-access-token', '')
        if not token:
            response = JSONResponse(
                {'error': 'Bearer access token이 필요합니다.'},
                status_code=401,
                headers={'WWW-Authenticate': 'Bearer', 'Cache-Control': 'no-store'},
            )
            await response(scope, receive, send)
            return

        try:
            authorized = validate_mcp_agent_token(token, self.config, self.extensions)
        except RuntimeError:
            logger.error('MCP Entra 인증 설정이 누락되었습니다.')
            response = JSONResponse({'error': 'MCP Entra 인증이 설정되지 않았습니다.'}, status_code=503)
        except PyJWKClientConnectionError:
            logger.exception('MCP Entra signing keys could not be retrieved.')
            response = JSONResponse({'error': 'Entra 인증 서비스를 사용할 수 없습니다.'}, status_code=503)
        else:
            if not authorized:
                response = JSONResponse(
                    {'error': 'MCP 호출 권한이 없습니다.'},
                    status_code=403,
                    headers={'Cache-Control': 'no-store'},
                )
            else:
                await self.app(scope, receive, send)
                return

        await response(scope, receive, send)


class McpPathMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope.get('path') == '/mcp':
            scope = {**scope, 'path': '/mcp/'}
        await self.app(scope, receive, send)


def create_mcp_asgi_app(flask_app):
    mcp_http_app = mcp.streamable_http_app()
    mcp_http_app.add_middleware(
        McpAuthMiddleware,
        config=flask_app.config,
        extensions=flask_app.extensions,
    )

    @asynccontextmanager
    async def lifespan(_app):
        async with mcp.session_manager.run():
            yield

    app = Starlette(
        routes=[
            Mount('/mcp', app=mcp_http_app),
            Mount('/', app=WSGIMiddleware(flask_app)),
        ],
        lifespan=lifespan,
    )
    return McpPathMiddleware(app)
