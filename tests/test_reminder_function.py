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