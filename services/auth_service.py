"""Validate the company-tenant ID token supplied by App Service authentication."""

import uuid
from urllib.parse import urlsplit

import jwt
from flask import abort, current_app, jsonify, make_response, render_template, request
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError


def _origin(value):
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ''
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'.lower()


def _authentication_required():
    if request.path.startswith('/api/'):
        response = make_response(jsonify(error='로그인이 필요합니다.', code='authentication_required'), 401)
    elif request.method == 'GET' and request.blueprint in ('main', 'roster'):
        response = make_response(render_template('auth_recovery.html'), 401)
    else:
        abort(401)
    response.headers['Cache-Control'] = 'no-store'
    return response


def validate_mcp_agent_token(token, config, extensions):
    """Validate an app-only access token with the MCP API role."""
    tenant = config.get('EMPLOYEE_TENANT_ID', '').lower()
    audience = config.get('MCP_API_AUDIENCE', '')
    required_role = config.get('MCP_REQUIRED_ROLE', '')
    if not tenant or not audience or not required_role:
        raise RuntimeError('MCP Entra authentication is not configured')
    if len(token) > 32768:
        return False

    try:
        uuid.UUID(tenant)
    except ValueError as error:
        raise RuntimeError('MCP Entra tenant is invalid') from error

    issuer = f'https://login.microsoftonline.com/{tenant}/v2.0'
    try:
        jwks = extensions.setdefault(
            'timetable_jwks',
            PyJWKClient(f'https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys', timeout=5),
        )
        key = jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            audience=audience,
            issuer=issuer,
            options={'require': ['iss', 'aud', 'sub', 'iat', 'nbf', 'exp', 'tid', 'oid', 'roles']},
        )
    except PyJWKClientConnectionError:
        raise
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        return False

    roles = claims.get('roles')
    return (
        isinstance(claims.get('tid'), str)
        and claims['tid'].lower() == tenant
        and isinstance(roles, list)
        and required_role in roles
    )


def require_company_user():
    config = current_app.config
    if config['AUTH_MODE'] == 'local':
        if config.get('WEBSITE_SITE_NAME'):
            abort(503)
        return
    if config['AUTH_MODE'] != 'entra':
        abort(503)

    tenant = config['EMPLOYEE_TENANT_ID'].lower()
    client = config['LOGIN_CLIENT_ID'].lower()
    domain = config['LOGIN_DOMAIN'].lower()
    origin = _origin(config['APP_ORIGIN'])
    try:
        uuid.UUID(tenant)
        uuid.UUID(client)
    except (ValueError, AttributeError):
        abort(503)
    if not domain or not origin or not origin.startswith('https://'):
        abort(503)

    token = request.headers.get('X-MS-TOKEN-AAD-ID-TOKEN', '')
    if not token:
        return _authentication_required()
    if len(token) > 32768:
        return _authentication_required()
    issuer = f'https://login.microsoftonline.com/{tenant}/v2.0'
    try:
        jwks = current_app.extensions.setdefault(
            'timetable_jwks', PyJWKClient(f'https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys', timeout=5)
        )
        key = jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=client, issuer=issuer,
                            options={'require': ['iss', 'aud', 'sub', 'iat', 'nbf', 'exp', 'tid', 'oid']})
        uuid.UUID(claims['oid'])
    except PyJWKClientConnectionError:
        abort(503)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        return _authentication_required()

    username = claims.get('preferred_username')
    if (not isinstance(claims['tid'], str) or claims['tid'].lower() != tenant
            or type(claims.get('acct')) not in (int, str) or claims['acct'] not in (0, '0')
            or claims.get('idtyp') == 'app' or not isinstance(username, str)
            or not username.lower().endswith('@' + domain)):
        abort(403)

    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        source = request.headers.get('Origin') or request.headers.get('Referer', '')
        if _origin(source) != origin:
            abort(403)