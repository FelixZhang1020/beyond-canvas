"""Startup must prepare sketch understanding even with hosted mesh generation."""
from types import SimpleNamespace

import pytest

from studio import start


@pytest.mark.parametrize('available', [True, False])
def test_api_default_never_loads_mac_models(monkeypatch, tmp_path, available):
    from studio.core import deployment_checks
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    monkeypatch.setattr(start.os, 'chdir', lambda path: None)
    monkeypatch.setattr(start, 'load_dotenv', lambda: None)
    monkeypatch.setattr(start, 'ready', lambda url: True)
    monkeypatch.setattr(deployment_checks, 'check_slot', lambda slot: {
        'slot': slot.slot, 'status': 'ready' if available else 'unavailable'})
    monkeypatch.setattr(start.subprocess, 'run', lambda *a, **kw: pytest.fail('local model startup'))
    assert start.main(['--check']) == (0 if available else 1)


def test_api_launch_uses_lightweight_runtime_and_preserves_selection(monkeypatch, tmp_path):
    from studio.core import deployment_checks
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    monkeypatch.setattr(start.os, 'chdir', lambda path: None)
    monkeypatch.setattr(start, 'load_dotenv', lambda: None)
    monkeypatch.setattr(start, 'ready', lambda url: ':7290/' in url)
    monkeypatch.setattr(deployment_checks, 'check_slot', lambda slot: {'slot': slot.slot, 'status': 'ready'})
    calls = []
    monkeypatch.setattr(start.subprocess, 'run', lambda command, **kw: calls.append(command))
    monkeypatch.setattr(start.os, 'execv', lambda executable, command: calls.append(command))
    assert start.main(['--deployment', 'stepfun']) == 0
    assert calls[0] == ['sh', 'studio/page/build.sh']
    command = calls[1]
    assert command[command.index('--profile') + 1] == 'stepfun'
    assert '--speech-provider' not in command
    assert command[command.index('--deployment') + 1] == 'stepfun'
    assert len(calls) == 2


def test_legacy_current_requires_explicit_choice(monkeypatch, tmp_path):
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    monkeypatch.setattr(start.os, 'chdir', lambda path: None)
    monkeypatch.setattr(start, 'load_dotenv', lambda: None)
    (tmp_path / '.studio').mkdir()
    (tmp_path / '.studio/deployment.json').write_text('{"deployment":"current"}')
    with pytest.raises(RuntimeError, match='ambiguous'):
        start.main(['--check'])


def _reports(monkeypatch, tmp_path, results):
    """Stand in for check_profile so a machine's real hardware does not decide the test."""
    from studio import start as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module.os, 'chdir', lambda path: None)
    monkeypatch.setattr(module, 'load_dotenv', lambda: None)

    def check_profile(name):
        return {'target': name, 'ready': results[name],
                'components': [{'slot': 'image.edit', 'status': 'ready' if results[name] else 'unavailable'}]}

    # Patched where main() reads it: it does `from studio.core.deployment_checks import
    # check_profile` on every call, so patching the name on studio.start does nothing.
    monkeypatch.setattr('studio.core.deployment_checks.check_profile', check_profile)


def test_a_machine_without_the_gpu_box_refuses_and_names_what_is_missing(monkeypatch, tmp_path, capsys):
    """A first run without the GPU box used to fall back to API First, which
    needed no hardware. API First was archived, so there is nothing
    to fall back to: the check fails and prints the component that is missing."""
    _reports(monkeypatch, tmp_path, {'stepfun': False})
    assert start.main(['--check']) == 1
    said = capsys.readouterr().out
    assert 'image.edit: unavailable' in said and 'instead' not in said


def test_a_copy_without_a_stepfun_key_is_told_which_key_and_where_it_goes(monkeypatch, tmp_path, capsys):
    """Operator: whoever pulls the project brings their own keys; the check said only
    which slots were down, never which key would bring them up."""
    _reports(monkeypatch, tmp_path, {'stepfun': False})
    monkeypatch.delenv('STEPFUN_API_KEY', raising=False)
    start.main(['--check'])
    said = capsys.readouterr().out
    assert 'no STEPFUN_API_KEY on this machine' in said and 'copy .env.example to .env' in said
    monkeypatch.setenv('STEPFUN_API_KEY', 'not-a-real-key')
    start.main(['--check'])
    assert 'STEPFUN_API_KEY' not in capsys.readouterr().out


@pytest.mark.parametrize('name,label', [('api', 'API First'), ('local-first', 'Local First')])
def test_asking_for_an_archived_deployment_says_it_was_archived(monkeypatch, tmp_path, name, label):
    _reports(monkeypatch, tmp_path, {'stepfun': True})
    with pytest.raises(RuntimeError, match=f'{label} was archived;'):
        start.main(['--check', '--deployment', name])


def test_a_saved_archived_choice_starts_stepfun_first(monkeypatch, tmp_path, capsys):
    _reports(monkeypatch, tmp_path, {'stepfun': True})
    (tmp_path / '.studio').mkdir()
    (tmp_path / '.studio/deployment.json').write_text('{"deployment":"local-first"}')
    assert start.main(['--check']) == 0
    assert 'Local First was archived; starting StepFun First.' in capsys.readouterr().out
