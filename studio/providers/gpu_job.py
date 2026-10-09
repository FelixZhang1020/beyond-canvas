"""Carry a classroom cancellation only to its own private GPU job."""
from contextlib import contextmanager
from contextvars import ContextVar
import threading
import uuid

import httpx

from studio.core.errors import ModelUnavailable

cancelled_request = ContextVar('gpu_cancelled_request', default=None)


@contextmanager
def stream_job(client, base_url, path, body, timeout, cancelled=None):
    cancelled = cancelled or cancelled_request.get()
    if cancelled is None:
        with client.stream('POST', base_url + path, json=body, timeout=timeout) as response:
            yield response
        return
    if cancelled():
        raise ModelUnavailable('GPU request cancelled before submission')
    job_id = str(uuid.uuid4())
    finished = threading.Event()

    def cancel():
        try:
            with httpx.Client(trust_env=False, timeout=2) as control:
                control.post(base_url + '/v1/cancel', json={'job_id': job_id})
        except httpx.HTTPError:
            pass  # The worker still enforces its bounded lifetime.

    def watch():
        while not finished.wait(0.1):
            if cancelled():
                cancel()
                return

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    completed = False
    try:
        with client.stream('POST', base_url + path, json=dict(body, job_id=job_id), timeout=timeout) as response:
            yield response
        completed = True
    finally:
        finished.set()
        watcher.join(timeout=2.5)
        if not completed:
            cancel()
            if cancelled():
                # Whatever the worker answered while being told to stop is its
                # reaction to the cancel, not a verdict on the drawing. In one
                # live run a teacher pressed stop 30 s into a mesh job and the
                # ledger recorded "local mesh worker is busy or unavailable" —
                # a broken worker, to anyone reading it, where there was none.
                raise ModelUnavailable('stopped by the teacher')
