"""Loopback media endpoints with bounded jobs sharing the existing GPU lock.

Models run in disposable containers and release VRAM after each job. Only this
project's idle TRELLIS container is paused while holding its shared lock.
"""
import argparse
import base64
import fcntl
import json
import re
import select
import socket
import struct
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_REQUEST = 12 * 1024 * 1024
MODELS = {'image': ('flux', 'step1x'), 'mesh': ('pixal',), 'voice': ('VoxCPM2',), 'trellis': ('trellis2',), 'video': ('wan2.2-ti2v-5b',),
          'book': ('flux',)}
ROUTES = {'image': '/v1/image', 'mesh': '/v1/mesh', 'voice': '/v1/audio/speech', 'trellis': '/v1/mesh', 'video': '/v1/video',
          'book': '/v1/pictures'}
MIME = {'image': 'image/png', 'mesh': 'model/gltf-binary', 'voice': 'audio/wav', 'trellis': 'model/gltf-binary', 'video': 'video/mp4',
        'book': 'application/json'}
# A storybook's pages in a picture-book style: several pictures in one job, so the model loads
# once for all of them. Page 1 in four styles, or up to seven pages in one.
MOST_PICTURES = 8


# How long one job may queue and run, together. The studio's video slot waits exactly this long.
# It was 1200 until the class clip went from 3 s to 5 s (~18 min to make).
JOB_DEADLINE_S = 1500


def run(command, **kw):
    return subprocess.run(command, check=True, capture_output=True, timeout=kw.pop('timeout', 30), **kw)


def record_job(root, kind, job, cancelled):
    """One line per generation in media-extra/jobs.jsonl: which model, how long, how it ended.
    Never the request: no picture, no instruction, no words. Kept on the machine that ran the job."""
    outcome = job.get('outcome') or ('cancelled' if cancelled else 'failed')
    line = {'at': round(time.time(), 1), 'kind': kind, 'model': job['model'],
            'seconds': round(time.monotonic() - job['started'], 1), 'outcome': outcome, 'bytes': job.get('bytes')}
    with (root / 'media-extra' / 'jobs.jsonl').open('a') as handle:
        handle.write(json.dumps(line) + '\n')


def command(root, job, model, name):
    extra = root / 'media-extra'
    args = ['docker', 'run', '--rm', '--name', name, '--gpus', 'all', '--shm-size', '8g',
            '-e', 'HF_HUB_OFFLINE=1', '-e', 'TRANSFORMERS_OFFLINE=1', '-e', 'HF_MODULES_CACHE=/tmp/hf-modules',
            '-e', 'PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True',
            '-v', f'{job}:/job', '-v', f'{extra}/runner:/runner:ro']
    if model == 'flux':
        return args + ['-v', f'{root}/model-sync/models/flux2-klein-4b:/models/flux:ro',
                       '--entrypoint', 'python', 'beyond-canvas/pixal3d:f7cf384', '/runner/flux_worker.py']
    if model == 'VoxCPM2':
        voice_root = extra / ('voxcpm-download' if (extra / 'voxcpm-download/.pinned-revision').is_file() else 'voxcpm-model')
        return args + ['-v', f'{voice_root}:/models/voice:ro', '-v', f'{extra}/voices:/voices:ro',
                       'beyond-canvas/voxcpm2:f772e498']
    if model == 'step1x':
        return args + ['-v', f'{extra}/step1x-model:/models/step1x:ro',
                       'beyond-canvas/step1x:4cca05df']
    if model == 'trellis2':
        return args + ['-e', 'ATTN_BACKEND=flash_attn', '-e', 'SPARSE_ATTN_BACKEND=flash_attn',
            '-e', 'HF_HOME=/models/huggingface', '-v', f'{root}/trellis2/models:/models:ro',
            '-v', f'{root}/trellis2/source/trellis2/modules/image_feature_extractor.py:/app/trellis2/modules/image_feature_extractor.py:ro',
            '--entrypoint', 'python', 'beyond-canvas/trellis2:75fbf018-exr1', '/runner/trellis_worker.py']
    if model == 'wan2.2-ti2v-5b':
        prompt = json.loads((job / 'request.json').read_text())['instruction']
        return args + ['-v', f'{root}/model-sync/models/wan2.2-ti2v-5b:/models/wan:ro',
            'beyond-canvas/wan22-smoke:42bf4cfa', '--task', 'ti2v-5B', '--size', '1280*704',
            '--frame_num', '33', '--sample_steps', '10', '--ckpt_dir', '/models/wan',
            '--offload_model', 'True', '--convert_model_dtype', '--t5_cpu', '--image', '/job/input.png',
            '--prompt', prompt, '--base_seed', '42', '--save_file', '/job/output.mp4']
    pixal = root / 'pixal3d'
    return args + ['-e', 'NAF_REPO_PATH=/models/torch/hub/valeoai_NAF_main', '-e', 'TORCH_HOME=/models/torch',
        '-e', 'ATTN_BACKEND=flash_attn', '-v', f'{root}/trellis2/models/huggingface:/models/huggingface:ro', '-v', f'{pixal}/models/Pixal3D:/models/Pixal3D:ro',
        '-v', f'{pixal}/models/dinov3:/models/dinov3:ro', '-v', f'{pixal}/models/torch-host:/models/torch:ro',
        '-v', f'{pixal}/source/smoke_rgba.py:/opt/pixal3d/smoke_rgba.py:ro',
        '--entrypoint', 'python', 'beyond-canvas/pixal3d:f7cf384', '/runner/pixal_worker.py', '--image', '/job/input.png', '--output', '/job/output.glb',
        '--model-path', '/models/Pixal3D', '--dino-path', '/models/dinov3', '--seed', '42']


def gpu_busy():
    usage = run(['nvidia-smi', '--query-compute-apps=used_memory', '--format=csv,noheader,nounits']).stdout
    return sum(int(x) for x in usage.split() if x.isdigit()) > 1536


def room_for(model):
    """Whether a job for this model may start beside whatever else holds the GPU. On the 4090
    nothing else may: the card's own memory is the limit and a second process can starve it.
    deploy/spark/media_spark.py replaces this with a memory sum, because the Spark's chip draws
    on the machine's memory and other work there is not ours to wait for."""
    return not gpu_busy()


def memory_low():
    """Whether the machine is too short of memory to start or keep a job. Never on the
    4090, whose card has its own memory; deploy/spark/media_spark.py replaces this on
    the Spark, where the chip draws on the machine's memory and running out freezes it."""
    return False


def cleanup_job(name, process):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    # The Docker daemon may still be completing create after the client exits.
    # Remove only the UUID-named worker; two bounded confirmations cover that race.
    # Compared lowercased: Docker 29 on the Spark answers `error: no such object`
    # where the 4090's Docker says `No such object`.
    for _ in range(2):
        result = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)
        if result.returncode and b'no such container' not in result.stderr.lower():
            raise OSError('worker cleanup unconfirmed; legacy model stays paused')
        time.sleep(.5)
    result = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', name], capture_output=True, timeout=10)
    if result.returncode == 0 or b'no such object' not in result.stderr.lower():
        raise OSError('worker cleanup unconfirmed; legacy model stays paused')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def reply(self, status, body, mime='application/json'):
        if isinstance(body, dict): body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def disconnected(self):
        if getattr(self, "cancel_event", None) is not None and self.cancel_event.is_set():
            return True
        if select.select([self.connection], [], [], 0)[0]:
            return self.connection.recv(1, socket.MSG_PEEK) == b''
        return False

    def do_GET(self):
        if self.path != '/v1/models': return self.reply(404, {'error': 'unknown route'})
        rows = []
        for model in MODELS[self.server.kind]:
            ready = (self.server.root / 'media-extra' / f'{model}.ready').is_file()
            state = getattr(self.server, 'phase', 'standby') if getattr(self.server, 'active_model', None) == model else 'standby'
            row = {'id': model, 'ready': ready, 'state': state if ready else 'unavailable'}
            evidence = self.server.root / 'media-extra' / f'{model}.evidence.json'
            if evidence.is_file():
                row['last_generation'] = json.loads(evidence.read_text())
            rows.append(row)
        self.reply(200, {'data': rows, 'busy': self.server.busy.locked(), 'evidence': 'installed runtime and weights; generation evidence separate'})

    def do_POST(self):
        if self.path == '/v1/cancel':
            if self.headers.get('Origin') or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(403, {'error': 'server-to-server JSON only'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024: raise ValueError()
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict): raise ValueError()
                job_id = payload.get('job_id', '')
                if not isinstance(job_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', job_id): raise ValueError()
                with self.server.cancel_lock:
                    event = self.server.cancellations.get(job_id)
                    if event is None:
                        now = time.monotonic()
                        self.server.pending_cancels = {key: stamp for key, stamp in self.server.pending_cancels.items() if now - stamp < 120}
                        if len(self.server.pending_cancels) >= 128:
                            return self.reply(503, {'error': 'cancellation queue full'})
                        self.server.pending_cancels[job_id] = now
                    else:
                        event.set()
                return self.reply(200, {'cancelled': True, 'job_id': job_id})
            except (ValueError, TypeError): return self.reply(422, {'error': 'invalid cancellation'})
        if self.path != ROUTES[self.server.kind]: return self.reply(404, {'error': 'unknown route'})
        if self.headers.get('Origin') or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(403, {'error': 'server-to-server JSON only'})
        if not self.server.busy.acquire(False): return self.reply(503, {'error': 'worker queue full'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_REQUEST: raise ValueError()
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict): raise ValueError()
            job_id = payload.get('job_id', uuid.uuid4().hex)
            if not isinstance(job_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', job_id): raise ValueError()
            self.job_id, self.cancel_event = job_id, threading.Event()
            with self.server.cancel_lock:
                if job_id in self.server.cancellations: raise ValueError()
                self.server.cancellations[job_id] = self.cancel_event
                stamp = self.server.pending_cancels.pop(job_id, None)
                if stamp is not None and time.monotonic() - stamp < 120:
                    self.cancel_event.set()
            if self.cancel_event.is_set(): raise OSError("cancelled before queue")
            model = payload.get('model', 'VoxCPM2' if self.server.kind == 'voice' else '')
            if model not in MODELS[self.server.kind]: raise ValueError()
            if not (self.server.root / 'media-extra' / f'{model}.ready').is_file():
                return self.reply(503, {'error': 'model installation not verified'})
            if self.server.kind == 'voice':
                if payload.get('voice') not in ('gentle-female', 'gentle-male', 'soft-child', 'child'): raise ValueError()
                if not isinstance(payload.get('input'), str) or not 1 <= len(payload['input']) <= 1000: raise ValueError()
                # A storybook page in a child's copied voice (deploy/spark/voice_book_worker.py): the first answer the
                # child said about the drawing, a WAV of at most ten seconds, sent with the page and never logged.
                if payload['voice'] == 'child':
                    reference = base64.b64decode(str(payload.get('reference', '')), validate=True)
                    if not 1024 <= len(reference) <= 2*1024*1024 or reference[:4] != b'RIFF': raise ValueError()
                    if not isinstance(payload.get('reference_text', ''), str) or len(payload.get('reference_text', '')) > 1000: raise ValueError()
            elif self.server.kind == 'book':
                pictures = payload.get('pictures')
                if not isinstance(pictures, list) or not 1 <= len(pictures) <= MOST_PICTURES: raise ValueError()
                for picture in pictures:
                    if not isinstance(picture, dict) or not 1 <= len(picture.get('instruction') or '') <= 4000: raise ValueError()
                    head, sep, data = str(picture.get('image', '')).partition(',')
                    if not head.startswith('data:image/') or not head.endswith(';base64') or not sep: raise ValueError()
                    if not 256 <= len(base64.b64decode(data, validate=True)) <= 8*1024*1024: raise ValueError()
                    seed = picture.get('seed', 42)
                    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2 ** 31: raise ValueError()
            else:
                uri = payload.get('image', '')
                if not isinstance(uri, str): raise ValueError()
                head, sep, data = uri.partition(',')
                if not head.startswith('data:image/') or not head.endswith(';base64') or not sep: raise ValueError()
                image = base64.b64decode(data, validate=True)
                if not 256 <= len(image) <= 8*1024*1024: raise ValueError()
                if self.server.kind in ('image', 'video') and (not isinstance(payload.get('instruction'), str) or not 1 <= len(payload['instruction']) <= 4000): raise ValueError()
            # restart.sh counts the job folders holding this lock and stops services before letting go
            # (code review), so a job is either counted or made after the restart, never lost
            # between the two. Held only while the folder is made; the job itself does not wait on it.
            with (self.server.root / 'restart.lock').open('a+b') as gate:
                fcntl.flock(gate, fcntl.LOCK_SH)
                made = tempfile.TemporaryDirectory(prefix='media-', dir=self.server.root / 'media-extra/jobs')
            with made as folder:
                job = Path(folder)
                (job / 'request.json').write_text(json.dumps(payload))
                if self.server.kind not in ('voice', 'book'): (job / 'input.png').write_bytes(image)
                self.server.active_model, self.server.phase = model, 'queued'
                started = time.monotonic()
                self.job = {'model': model, 'started': started}
                self.generate(job, model)
                suffix = {'image':'png', 'mesh':'glb', 'voice':'wav', 'trellis':'glb', 'video':'mp4', 'book':'json'}[self.server.kind]
                output = (job / f'output.{suffix}').read_bytes()
                if not 32 <= len(output) <= (16 if suffix == 'json' else 8)*1024*1024: raise OSError('output budget')
                if suffix == 'json':
                    drawn = json.loads(output).get('pictures')
                    if not isinstance(drawn, list) or len(drawn) != len(payload['pictures']): raise OSError('picture count')
                    if any(not base64.b64decode(p, validate=True).startswith(b'\xff\xd8\xff') for p in drawn): raise OSError('invalid JPEG')
                if suffix == 'png' and not output.startswith(b'\x89PNG\r\n\x1a\n'): raise OSError('invalid PNG')
                if suffix == 'glb' and (output[:4] != b'glTF' or struct.unpack_from('<II', output, 4) != (2, len(output))): raise OSError('invalid GLB')
                if suffix == 'wav' and (output[:4] != b'RIFF' or output[8:12] != b'WAVE'): raise OSError('invalid WAV')
                if suffix == 'mp4' and output[4:8] != b'ftyp': raise OSError('invalid MP4')
                receipt = {'model': model, 'verified_at': datetime.now(timezone.utc).isoformat(),
                           'elapsed_seconds': round(time.monotonic() - started, 3), 'bytes': len(output),
                           'scope': 'generated valid bytes; quality requires review'}
                (self.server.root / 'media-extra' / f'{model}.evidence.json').write_text(json.dumps(receipt))
                self.job.update(outcome='ok', bytes=len(output))
                self.close_job()
                self.reply(200, output, MIME[self.server.kind])
        except (ValueError, TypeError, KeyError):
            self.close_job()
            self.reply(422, {'error': 'invalid bounded media request'})
        except (OSError, subprocess.SubprocessError):
            self.close_job()
            try: self.reply(503, {'error': 'GPU job unavailable; see project service log'})
            except OSError: pass
        finally:
            self.close_job()
            if hasattr(self, "job_id"):
                with self.server.cancel_lock:
                    self.server.cancellations.pop(self.job_id, None)
            self.server.active_model, self.server.phase = None, 'standby'
            self.server.busy.release()

    def close_job(self):
        """Record the running job once, before its answer goes out, so the line exists when the caller reads."""
        job, self.job = getattr(self, 'job', None), None
        if job:
            try: record_job(self.server.root, self.server.kind, job, self.cancel_event.is_set())
            except OSError: pass  # a full disk must not also fail the job or keep the queue locked

    def generate(self, job, model):
        deadline = time.monotonic() + JOB_DEADLINE_S
        with (self.server.root / 'gpu.lock').open('a+b') as lock:
            while True:
                if self.disconnected() or time.monotonic() > deadline: raise OSError('cancelled or queue timeout')
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError: time.sleep(.25)
            # The persistent legacy 3D app also uses this lock for its jobs. A machine
            # that never had it (the Spark) has nothing to pause: a missing container
            # reads as not running instead of failing every job.
            state = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', 'beyond-canvas-trellis2'],
                                   capture_output=True, timeout=30).stdout.strip()
            legacy_up = state == b'true'
            restore = False
            name = 'beyond-canvas-media-' + uuid.uuid4().hex[:12]
            process = None
            try:
                # Speech is asked for many times a lesson and needs little VRAM,
                # and stopping the 3D app costs 10.7 s every single time: it
                # declares no stop signal, so Docker waits out the whole timeout
                # and then kills it. As measured, an idle TRELLIS holds no
                # CUDA memory at all, so for speech that wait freed nothing and the
                # teacher paid it per sentence. Every other kind still stops it
                # unconditionally; speech pays only when the card is truly occupied,
                # and the guard below stays the thing that actually protects a job.
                if legacy_up and (self.server.kind != 'voice' or gpu_busy()):
                    run(['docker', 'stop', 'beyond-canvas-trellis2'], timeout=60)
                    restore = True
                if not room_for(model): raise OSError('other GPU work leaves no room for this job')
                if memory_low(): raise OSError('free memory below the floor; job not started')
                with (job / 'worker.log').open('wb') as log:
                    self.server.phase = 'running'
                    process = subprocess.Popen(command(self.server.root, job, model, name), stdout=log, stderr=log)
                    while process.poll() is None:
                        if self.disconnected() or time.monotonic() > deadline:
                            raise OSError('cancelled or job timeout')
                        if memory_low():
                            raise OSError('free memory fell below the floor; worker stopped')
                        time.sleep(.25)
                    if process.returncode: raise OSError('worker failed')
            finally:
                # If cleanup cannot prove our worker stopped, do not restore another GPU model.
                cleanup_job(name, process)
                log_path = job / 'worker.log'
                if log_path.is_file() and log_path.stat().st_size <= 8*1024*1024:
                    log_text = log_path.read_text(errors='replace')
                    payload = json.loads((job / 'request.json').read_text())
                    asked = [payload] + [p for p in payload.get('pictures') or () if isinstance(p, dict)]
                    for key, value in ((key, one.get(key)) for one in asked for key in ('instruction', 'input', 'image', 'reference', 'reference_text')):
                        if isinstance(value, str) and value:
                            for form in (value, repr(value)[1:-1], json.dumps(value)[1:-1]):
                                log_text = log_text.replace(form, '[request content omitted]')
                    (self.server.root / 'media-extra' / f'{model}-last.log').write_text(log_text[-64000:])
                if restore: run(['docker', 'start', 'beyond-canvas-trellis2'], timeout=60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=MODELS, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    if not 7000 <= args.port <= 7700 or args.port % 10: raise SystemExit('invalid studio port')
    (args.root / 'media-extra/jobs').mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.kind, server.root, server.busy = args.kind, args.root, threading.Lock()
    server.cancellations, server.cancel_lock = {}, threading.Lock()
    server.pending_cancels = {}
    server.serve_forever()

if __name__ == '__main__': main()
