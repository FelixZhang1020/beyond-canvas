"""Console reads live state without booting models or disclosing request content."""
from types import SimpleNamespace
from io import BytesIO
import json
from studio.server.console_panel import PARTS, progress, serve_console
from studio.server.serve_showpiece import ShowpieceHolder
from studio.server.stream import Stream


def test_idle_console_does_not_initialize_showpiece():
    holder = ShowpieceHolder()
    holder._build = lambda: (_ for _ in ()).throw(AssertionError('must not boot'))
    assert progress(SimpleNamespace(showpiece=holder)) == []
    assert holder._driver is None


def test_progress_reports_stages_and_completion_without_content():
    stream = Stream()
    request = SimpleNamespace(skill='art-feedback', stream=stream)
    server = SimpleNamespace(classroom=SimpleNamespace(requests={'a': request}))
    stream.emit('stage', {'stage': 'studio-safety', 'status': 'running', 'message': 'private input'})
    row = progress(server)[0]
    assert row['done'] is False and row['stage'] == 'studio-safety'
    assert 'private input' not in json.dumps(row)
    stream.emit('done', {'status': 'stopped', 'reason_code': 'model_unavailable'})
    stream.finish()
    assert progress(server)[0]['done'] is True
    assert progress(server)[0]['status'] == 'stopped'


def test_active_jobs_are_not_hidden_by_completed_history():
    requests = {}
    for i in range(20):
        stream = Stream()
        if i: stream.finish()
        requests[str(i)] = SimpleNamespace(skill=f'skill-{i}', stream=stream)
    rows = progress(SimpleNamespace(classroom=SimpleNamespace(requests=requests)))
    assert rows[0]['skill'] == 'skill-0' and not rows[0]['done']
    assert len(rows) == 4


def test_routes_are_exact_and_read_only(monkeypatch):
    monkeypatch.setattr('studio.showpiece.routes.machine_stats', lambda: {'cpu_percent': 12})
    monkeypatch.setattr('studio.ops.spark_monitor.picture', lambda: {'now': [], 'finished': [], 'today': {}})
    class Handler:
        path = '/api/console'
        server = SimpleNamespace()
        headers = {}
        wfile = BytesIO()
        def send_response(self, status): self.status = status
        def send_header(self, *args): pass
        def end_headers(self): pass
    h = Handler()
    assert serve_console(h) and h.status == 200
    assert json.loads(h.wfile.getvalue()) == {'machine': {'cpu_percent': 12}, 'jobs': [], 'parts': PARTS,
                                              'services': [], 'sources': [],
                                              'chip': {'now': [], 'finished': [], 'today': {}}}
    h.path = '/console.js'
    h.wfile = BytesIO()
    assert serve_console(h) and b'window.Backstage' in h.wfile.getvalue()
    h.path = '/console.js/../secrets'
    assert not serve_console(h)


def test_only_reported_valid_percent_is_shown_and_new_stage_clears_it():
    stream = Stream()
    request = SimpleNamespace(skill='animation', stream=stream)
    server = SimpleNamespace(classroom=SimpleNamespace(requests={'a': request}))
    for percent, expected in [(42, 42), (0, 0), (100, 100), (-1, None), (101, None), (float('nan'), None), (True, None), ('50', None)]:
        stream.emit('stage', {'stage': 'render', 'status': 'running', 'partial': {'percent': percent}})
        assert progress(server)[0]['percent'] == expected
    stream.emit('stage', {'stage': 'judge', 'status': 'running'})
    assert progress(server)[0]['percent'] is None


def test_classroom_modules_use_reported_events_and_do_not_export_content():
    stream = Stream()
    server = SimpleNamespace(classroom=SimpleNamespace(requests={
        'r1': SimpleNamespace(skill='art-feedback', stream=stream)}))
    stream.emit('stage', {'stage': 'studio-safety', 'status': 'running'})
    stream.emit('stage', {'stage': 'studio-safety', 'status': 'gate_pass',
                         'ledger': {'wall_s': 0.5, 'note': 'SECRET', 'outputs_path': '/SECRET'}})
    stream.emit('stage', {'stage': 'art-feedback', 'status': 'running', 'partial': {'text': 'SECRET'}})
    row = progress(server)[0]
    assert row['id'] == 'classroom:r1'
    assert row['processes'] == [
        {'name': 'studio-safety', 'status': 'gate_pass', 'seconds': 0.5, 'events': 2},
        {'name': 'art-feedback', 'status': 'running', 'seconds': None, 'events': 1}]
    assert len(row['events']) == 3 and 'SECRET' not in json.dumps(row)
    assert 'evals' not in row['parts'], 'do not infer an evaluation before its event'
    stream.emit('stage', {'stage': 'rubric', 'status': 'gate_fail'})
    assert progress(server)[0]['parts']['evals'] == 'gate_fail'
    for i in range(40):
        stream.emit('stage', {'stage': 'art-feedback', 'status': 'running'})
    row = progress(server)[0]
    assert len(row['events']) == 30
    assert row['processes'][1]['events'] == 41, 'tail limits must not discard process tallies'


def test_showpiece_live_context_is_separate_and_only_contains_safe_metadata():
    from threading import Condition
    run = SimpleNamespace(cond=Condition(), done=False, busy={'phase': 'tool', 'skill': 'structure-tour', 'args': 'SECRET'},
                          events=[{'kind': 'think', 'text': 'SECRET'},
                                  {'kind': 'act', 'skill': 'model-anatomy', 'seconds': 3.5, 'files': ['SECRET']}])
    row = progress(SimpleNamespace(driver=SimpleNamespace(runs={'r2': run})))[0]
    assert row['source'] == 'showpiece' and row['id'] == 'showpiece:r2'
    assert row['processes'][-1]['status'] == 'running'
    assert row['processes'][1]['seconds'] == 3.5
    assert 'SECRET' not in json.dumps(row)


def fake_service(monkeypatch, answers):
    """Stand in for the media services' `/v1/models`, keyed by base_url."""
    import studio.making.media_services as services
    services._cached.clear()
    asked = []

    def ask(url):
        asked.append(url)
        answer = answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(services, 'ask', ask)
    return services, asked


def test_a_clip_running_for_another_class_is_shown_not_hidden(monkeypatch):
    """Reported: the panel said the studio was idle through a ten-minute render.

    The class that asked for that clip had ended, so its request was gone from `progress`, while
    the service worked on to the finish. What the machine is making belongs to the machine.
    """
    services, _ = fake_service(monkeypatch, {'http://127.0.0.1:7260': {
        'busy': True, 'data': [{'id': 'wan2.2-i2v-a14b', 'ready': True, 'state': 'running',
                                'last_generation': {'model': 'wan2.2-i2v-a14b', 'elapsed_seconds': 731.4,
                                                    'verified_at': '2026-09-23T05:21:00+00:00',
                                                    'scope': 'generated valid bytes'}}]}})
    monkeypatch.setattr(services, 'endpoints', lambda name: {'http://127.0.0.1:7260': ['video.animation']})
    row = services.snapshot('stepfun')[0]
    assert row['answering'] and row['busy'] and row['phase'] == 'running'
    assert row['model'] == 'wan2.2-i2v-a14b' and row['slots'] == ['video.animation']


def test_a_resting_service_says_so_and_names_no_finished_job_as_the_last_one(monkeypatch):
    """The service's receipt is of its last *finished* job; after a cancelled clip that named one two days
    old. How the last job ended comes from the Spark's monitor now, so none of it is passed on."""
    services, _ = fake_service(monkeypatch, {'http://127.0.0.1:7240': {
        'busy': False, 'data': [{'id': 'trellis2', 'ready': True, 'state': 'standby',
                                 'last_generation': {'model': 'trellis2', 'elapsed_seconds': 69.5,
                                                     'verified_at': '2026-09-23T05:07:14+00:00',
                                                     'bytes': 3140000, 'output_path': '/home/someone/child.glb'}}]}})
    monkeypatch.setattr(services, 'endpoints', lambda name: {'http://127.0.0.1:7240': ['mesh.portrait']})
    row = services.snapshot('stepfun')[0]
    assert row['phase'] == 'standby' and row['model'] == 'trellis2'
    assert 'last' not in row and '69.5' not in json.dumps(row) and 'child.glb' not in json.dumps(row)


def test_a_service_that_does_not_answer_says_so_rather_than_vanishing(monkeypatch):
    import urllib.error
    services, _ = fake_service(monkeypatch, {'http://127.0.0.1:7270': urllib.error.URLError('refused')})
    monkeypatch.setattr(services, 'endpoints', lambda name: {'http://127.0.0.1:7270': ['image.edit']})
    row = services.snapshot('stepfun')[0]
    assert row['answering'] is False and row['model'] is None and row['slots'] == ['image.edit']


def test_the_panel_does_not_ask_the_services_again_on_every_two_second_poll(monkeypatch):
    services, asked = fake_service(monkeypatch, {'http://127.0.0.1:7260': {'busy': False, 'data': []}})
    monkeypatch.setattr(services, 'endpoints', lambda name: {'http://127.0.0.1:7260': ['video.animation']})
    for _ in range(5):
        services.snapshot('stepfun')
    assert asked == ['http://127.0.0.1:7260']


def test_only_services_on_this_machine_are_asked():
    from studio.making.media_services import endpoints
    found = endpoints('stepfun')
    assert found, 'the shipping deployment runs media on this machine'
    assert all(url.startswith('http://127.0.0.1:') for url in found), found
    assert endpoints('no-such-deployment') == {}


def test_a_showpiece_server_without_a_classroom_asks_no_service(monkeypatch):
    import studio.making.media_services as services
    monkeypatch.setattr(services, 'ask', lambda url: (_ for _ in ()).throw(AssertionError('must not ask')))
    assert services.snapshot(None) == []


def test_the_console_script_is_compressed_and_kept_like_the_page():
    """It used to be sent whole on every visit: 29 KB each time over a link measured at 5 KB/s."""
    sent = {}
    class Handler:
        path = '/console.js'
        server = SimpleNamespace()
        headers = {'Accept-Encoding': 'gzip, br'}
        def __init__(self): self.wfile = BytesIO()
        def send_response(self, status): sent['status'] = status
        def send_header(self, name, value): sent[name] = value
        def end_headers(self): pass
    first = Handler()
    assert serve_console(first) and sent['Content-Encoding'] == 'gzip' and sent['Cache-Control'] == 'no-cache'
    assert len(first.wfile.getvalue()) < 12000
    again = Handler()
    again.headers = {'Accept-Encoding': 'gzip, br', 'If-None-Match': sent['ETag']}
    assert serve_console(again) and sent['status'] == 304 and again.wfile.getvalue() == b''
