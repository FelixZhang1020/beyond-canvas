from unittest.mock import Mock
import httpx
import pytest
from studio.core import deployment_checks as checks
from studio.core.slots import SlotConfig


def test_missing_key_fails_without_network(monkeypatch):
    monkeypatch.delenv('STEPFUN_API_KEY', raising=False)
    monkeypatch.setattr(httpx, 'Client', Mock(side_effect=AssertionError('network')))
    assert checks.check_slot(SlotConfig('vlm.studio', 'stepfun', 'step-3.7-flash', {}))['status'] == 'unavailable'


@pytest.mark.parametrize('status,body,expected', [
    (200, {'data': [{'id': 'step-3.7-flash'}]}, 'ready'),
    (200, {'data': []}, 'unknown'),
    (401, {}, 'unavailable'), (503, {}, 'unavailable'),
])
def test_catalog_controls(monkeypatch, status, body, expected):
    monkeypatch.setenv('STEPFUN_API_KEY', 'test-secret')
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.get.return_value = httpx.Response(status, json=body)
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client)
    result = checks.check_slot(SlotConfig('vlm.studio', 'stepfun', 'step-3.7-flash', {}))
    assert result['status'] == expected
    assert 'test-secret' not in str(result)


@pytest.mark.parametrize('ready', [True, False])
def test_http_switch_is_gated(monkeypatch, ready):
    from studio.serve import StudioHandler
    handler = object.__new__(StudioHandler)
    room = Mock()
    room.deployment_status.return_value = {'selected': 'current'}
    room.switch_deployment.return_value = {'selected': 'stepfun'}
    handler.server = Mock(classroom=room)
    handler._json_body = lambda: {'deployment': 'stepfun'}
    handler._json = Mock()
    monkeypatch.setattr(checks, 'check_deployment', lambda *args: {'ready': ready, 'components': []})
    handler._select_deployment()
    assert room.switch_deployment.called == ready
    assert handler._json.call_args.args[1]['switched'] == ready
