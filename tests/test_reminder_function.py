from datetime import datetime, timezone
from types import SimpleNamespace

import function_app


def test_timer_binding_and_worker_wiring(monkeypatch):
    function = function_app.app.get_functions()[0]
    assert function.get_function_name() == 'reminder_timer'
    binding = function.get_bindings_dict()['bindings'][0]
    assert binding['schedule'] == '0 0 * * * *'
    assert binding['useMonitor'] is True
    assert binding['runOnStartup'] is False

    class FixedClock:
        @staticmethod
        def now(tz):
            return datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc)

    container = object()
    calls = []
    monkeypatch.setattr(function_app, 'datetime', FixedClock)
    monkeypatch.setenv('AZURE_CLIENT_ID', 'identity-id')
    monkeypatch.setenv('COSMOS_DB_ENDPOINT', 'https://example.documents.azure.com')
    monkeypatch.setenv('MAIL_TENANT_ID', 'tenant')
    monkeypatch.setenv('MAIL_CLIENT_ID', 'mail-app')
    monkeypatch.setenv('MAIL_CLIENT_SECRET', 'secret')
    monkeypatch.setattr(function_app, 'ManagedIdentityCredential', lambda client_id: ('identity', client_id))
    monkeypatch.setattr(function_app, 'CosmosClient', lambda endpoint, credential: SimpleNamespace(
        get_database_client=lambda database: SimpleNamespace(get_container_client=lambda name: container)))
    monkeypatch.setattr(function_app, 'ClientSecretCredential', lambda **kwargs: SimpleNamespace(
        get_token=lambda scope: SimpleNamespace(token='graph-token')))
    monkeypatch.setattr(function_app, 'CosmosStorage', lambda value: SimpleNamespace(
        get_all_courses=lambda: [{'id': 'course'}]))
    monkeypatch.setattr(function_app, 'CosmosReminderStorage', lambda value: ('store', value))
    monkeypatch.setattr(function_app, 'run_reminder_cycle', lambda *args: calls.append(args) or 0)

    function.get_user_function()(None)

    assert calls == [([{'id': 'course'}], ('store', container), 'elixirr@elixirr.co.kr', 'graph-token')]


def test_verification_reads_without_sending_or_writing(monkeypatch, caplog):
    class FixedClock:
        @staticmethod
        def now(tz):
            return datetime(2026, 10, 27, 20, 0, tzinfo=timezone.utc)

    container = object()
    calls = []
    monkeypatch.setattr(function_app, 'datetime', FixedClock)
    monkeypatch.setenv('REMINDER_VALIDATE_ONLY', 'true')
    monkeypatch.setenv('AZURE_CLIENT_ID', 'identity-id')
    monkeypatch.setenv('COSMOS_DB_ENDPOINT', 'https://example.documents.azure.com')
    monkeypatch.setattr(function_app, 'ManagedIdentityCredential', lambda client_id: ('identity', client_id))
    monkeypatch.setattr(function_app, 'CosmosClient', lambda endpoint, credential: SimpleNamespace(
        get_database_client=lambda database: SimpleNamespace(get_container_client=lambda name: container)))
    monkeypatch.setattr(function_app, 'CosmosStorage', lambda value: SimpleNamespace(
        get_all_courses=lambda: [{'id': 'course'}]))
    monkeypatch.setattr(function_app, 'CosmosReminderStorage', lambda value: SimpleNamespace(
        contacts=lambda: [{'id': 'contact'}],
        assignment=lambda course_id, entry_id: calls.append(('assignment', course_id, entry_id)),
        deliveries=lambda course_id, entry_id: calls.append(('deliveries', course_id, entry_id))))

    def reject_mail(*args, **kwargs):
        raise AssertionError('Verification must not request a mail token or send')

    monkeypatch.setattr(function_app, 'ClientSecretCredential', reject_mail)
    monkeypatch.setattr(function_app, 'run_reminder_cycle', reject_mail)
    monkeypatch.setattr(function_app.app, 'functions_bindings', {})
    with caplog.at_level('INFO'):
        function_app.app.get_functions()[0].get_user_function()(None)

    assert calls == [('assignment', '__verification__', '__verification__'),
                     ('deliveries', '__verification__', '__verification__')]
    assert 'Reminder verification succeeded: 1 courses, 1 contacts' in caplog.text