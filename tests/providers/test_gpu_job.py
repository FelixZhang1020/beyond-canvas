"""Cancellation addresses one submitted job and never a shared worker."""
from contextlib import contextmanager
import threading

import pytest

from studio.providers.gpu_job import cancelled_request, stream_job
from studio.core.errors import ModelUnavailable


class Client:
    def __init__(self): self.calls = []
    @contextmanager
    def stream(self, method, url, **kwargs):
        self.calls.append((url, kwargs))
        yield object()


def test_cancel_targets_only_the_current_submitted_job(monkeypatch):
    calls, sent, stopped = [], threading.Event(), threading.Event()
    class Control:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json): calls.append((url, json)); sent.set()
    monkeypatch.setattr('studio.providers.gpu_job.httpx.Client', Control)
    client = Client()
    token = cancelled_request.set(stopped.is_set)
    try:
        with stream_job(client, 'http://127.0.0.1:7270', '/v1/image', {'model':'flux'}, 10):
            stopped.set()
            assert sent.wait(2)
    finally:
        cancelled_request.reset(token)
    submitted = client.calls[0][1]['json']
    assert calls == [('http://127.0.0.1:7270/v1/cancel', {'job_id':submitted['job_id']})]
    assert submitted['model'] == 'flux'


def test_cancel_before_submission_never_starts_gpu_job():
    client = Client()
    with pytest.raises(ModelUnavailable):
        with stream_job(client, 'http://127.0.0.1:7270', '/v1/image', {}, 10, cancelled=lambda:True):
            pytest.fail('cancelled job ran')
    assert client.calls == []


def test_success_does_not_send_a_cancel(monkeypatch):
    def unexpected(**kwargs): pytest.fail('successful job was cancelled')
    monkeypatch.setattr('studio.providers.gpu_job.httpx.Client', unexpected)
    client = Client()
    with stream_job(client, 'http://127.0.0.1:7270', '/v1/image', {'model':'flux'}, 10, cancelled=lambda:False):
        pass
    assert len(client.calls) == 1


@pytest.fixture
def http_worker():
    """A loopback worker on test-only port 0, with no model or external API."""
    import json
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from types import SimpleNamespace
    from tests.making.test_animation import a_clip
    # A clip since the FLUX still picture was retired; it was a picture job until then.
    state = SimpleNamespace(submitted=[], cancelled=[], started=threading.Event(), release=threading.Event(),
                            payload=a_clip())
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path == '/v1/cancel':
                state.cancelled.append(body['job_id'])
                if state.submitted and body['job_id'] == state.submitted[0]['job_id']:
                    state.release.set()
                payload, status, mime=b'{}',200,'application/json'
            elif self.path == '/v1/video':
                state.submitted.append(body)
                state.started.set()
                state.release.wait(5)
                rejected = body['job_id'] in state.cancelled
                payload,status,mime=(b'{}',503,'application/json') if rejected else (state.payload,200,'video/mp4')
            else:
                payload,status,mime=b'{}',404,'application/json'
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            try: self.wfile.write(payload)
            except BrokenPipeError: pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    state.url=f'http://127.0.0.1:{server.server_port}'
    try: yield state
    finally:
        state.release.set()
        server.shutdown()
        server.server_close()
        thread.join(2)


@pytest.mark.parametrize('cancel_request',[True,False])
def test_classroom_cancel_reaches_blocked_http_job_and_releases_request(tmp_path,http_worker,cancel_request):
    import time
    from pathlib import Path
    from studio.classroom.classroom import Classroom
    from studio.providers.localvideo import LocalVideoClient
    from studio.providers.media import MediaSlot
    from tests.classroom.test_classroom import Scripted,ALLOW,DRAWING
    from tests.making.test_animation import CLEAN
    judge=Scripted([ALLOW]*6+[CLEAN])
    slot=MediaSlot(LocalVideoClient('wan2.2-i2v-a14b',{'base_url':http_worker.url,'timeout_s':8}),'to_video',{}, {})
    room=Classroom(tmp_path/'ledger',clients={'vlm.studio':judge,'vlm.director':judge},editor=slot)
    sid=room.begin({'language':'en','entrance':'colour'})
    did=room.add_drawing(sid,Path(DRAWING).read_bytes())
    rid=room.request(sid,'painting-to-animation',[did],{})['request_id']
    runner=threading.Thread(target=room.run_request,args=(rid,))
    try:
        runner.start()
        assert http_worker.started.wait(3), 'The job must reach the real loopback HTTP server first.'
        assert runner.is_alive(), 'The HTTP response must still be blocked at cancellation.'
        started=time.monotonic()
        if cancel_request:
            room.cancel(sid,rid)
        else:
            http_worker.release.set()
        runner.join(3.5)
        assert not runner.is_alive(), 'Cancellation must finish the in-flight request within the bound.'
        assert time.monotonic()-started < 3.5
        assert room.sessions[sid].make_lock.acquire(blocking=False), 'Finished request must release classroom lock.'
        room.sessions[sid].make_lock.release()
        submitted=http_worker.submitted[0]['job_id']
        assert isinstance(submitted,str) and submitted
        if cancel_request:
            assert http_worker.cancelled and set(http_worker.cancelled)=={submitted}
            done=[data for name,data in room.requests[rid].stream.updates if name=='done']
            assert any(d.get('reason_code')=='cancelled' for d in done)
            assert not any(d.get('status')=='done' for d in done)
        else:
            assert http_worker.cancelled==[]
            assert any(name=='done' and data.get('outputs') for name,data in room.requests[rid].stream.updates)
    finally:
        http_worker.release.set()
        runner.join(9)
        room.close()


def test_a_job_the_teacher_stopped_is_recorded_as_stopped_not_as_a_broken_worker(monkeypatch):
    """Seen live: stop pressed 30 s into a 3D job. The page said it had
    stopped; the ledger said "local mesh worker is busy or unavailable" — the
    worker's answer to being told to stop, read as its verdict on the drawing. A
    judge reading that ledger sees a broken worker where a teacher pressed a button.
    """
    class Control:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json): pass
    monkeypatch.setattr('studio.providers.gpu_job.httpx.Client', Control)
    client, pressed = Client(), [False]
    with pytest.raises(ModelUnavailable, match='stopped'):
        with stream_job(client, 'http://127.0.0.1:7240', '/v1/mesh', {'model': 'trellis2'}, 10,
                        cancelled=lambda: pressed[0]):
            pressed[0] = True
            # What localmesh raises when the worker answers the cancel with a 503.
            raise ModelUnavailable('local mesh worker is busy or unavailable')
