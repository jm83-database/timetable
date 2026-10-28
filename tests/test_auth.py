from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import create_app
from services import auth_service


TENANT = '11111111-1111-4111-8111-111111111111'
CLIENT = '22222222-2222-4222-8222-222222222222'
USER = '33333333-3333-4333-8333-333333333333'


@pytest.fixture
def auth_client():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    app = create_app()
    app.config.update(TESTING=True, AUTH_MODE='entra', EMPLOYEE_TENANT_ID=TENANT,
                      LOGIN_CLIENT_ID=CLIENT, LOGIN_DOMAIN='elixirr.co.kr',
                      APP_ORIGIN='https://timetable.example.com', WEBSITE_SITE_NAME='timetable')
    app.extensions['timetable_jwks'] = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))

    def token(**overrides):
        now = datetime.now(timezone.utc)
        claims = {'iss': f'https://login.microsoftonline.com/{TENANT}/v2.0', 'aud': CLIENT,
                  'sub': 'user', 'tid': TENANT, 'oid': USER, 'iat': now,
                  'nbf': now, 'exp': now + timedelta(minutes=5), 'acct': 0,
                  'preferred_username': 'employee@elixirr.co.kr'}
        claims.update(overrides)
        return jwt.encode(claims, key, algorithm='RS256')

    return app.test_client(), token


def test_requires_signed_company_member_token_for_pages_and_api(auth_client):
    client, token = auth_client
    assert client.get('/dashboard').status_code == 401
    assert client.get('/api/reminders/contacts').status_code == 401
    assert client.get('/dashboard', headers={'X-MS-TOKEN-AAD-ID-TOKEN': token()}).status_code == 200
    for changes in ({'acct': 1}, {'acct': None}, {'preferred_username': 'person@gmail.com'},
                    {'idtyp': 'app'}, {'tid': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'}):
        assert client.get('/dashboard', headers={'X-MS-TOKEN-AAD-ID-TOKEN': token(**changes)}).status_code == 403
    assert client.get('/dashboard', headers={'X-MS-TOKEN-AAD-ID-TOKEN': token(aud='wrong')}).status_code == 401


def test_writes_require_same_origin_and_azure_cannot_enable_local_mode(auth_client):
    client, token = auth_client
    headers = {'X-MS-TOKEN-AAD-ID-TOKEN': token()}
    assert client.post('/api/reminders/contacts', headers=headers, json={}).status_code == 403
    headers['Origin'] = 'https://other.example.com'
    assert client.post('/api/reminders/contacts', headers=headers, json={}).status_code == 403
    headers['Origin'] = 'https://timetable.example.com'
    assert client.post('/api/reminders/contacts', headers=headers, json={}).status_code == 400
    client.application.config['AUTH_MODE'] = 'local'
    assert client.get('/dashboard').status_code == 503


def test_uses_tenant_jwks_endpoint(auth_client, monkeypatch):
    client, token = auth_client
    keys = client.application.extensions.pop('timetable_jwks')
    urls = []

    def create_client(url, timeout):
        urls.append(url)
        return keys

    monkeypatch.setattr(auth_service, 'PyJWKClient', create_client)
    assert client.get('/dashboard', headers={'X-MS-TOKEN-AAD-ID-TOKEN': token()}).status_code == 200
    assert urls == [f'https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys']