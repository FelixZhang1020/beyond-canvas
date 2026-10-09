"""Contract tests use an ephemeral loopback server and a fake image worker."""
import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import subprocess
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('gpu_extra', Path(__file__).with_name('media_server.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Contracts(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        (root / 'media-extra/jobs').mkdir(parents=True)
        (root / 'media-extra/flux.ready').touch()
        self.calls = []
        calls = self.calls
        class Fake(module.Handler):
            def generate(self, job, model):
                calls.append(model)
                (job / 'output.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'png-test' * 10)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Fake)
        self.server.pending_cancels = {}
        self.server.cancellations, self.server.cancel_lock = {}, threading.Lock()
        self.server.root, self.server.kind, self.server.busy = root, 'image', threading.Lock()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    def request(self, model, job_id=None, **headers):
        payload = {'model': model, 'image': 'data:image/png;base64,' + base64.b64encode(b'x'*256).decode(), 'instruction': 'test'}
        if job_id: payload['job_id'] = job_id
        req = urllib.request.Request(self.url + '/v1/image', data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json', **headers})
        try:
            with self.opener.open(req) as response: return response.status, response.read()
        except urllib.error.HTTPError as error:
            with error: return error.code, error.read()

    def test_installed_model_generates_but_uninstalled_alternative_never_falls_back(self):
        self.assertEqual(self.request('flux')[0], 200)
        self.assertEqual(self.request('step1x')[0], 503)
        self.assertEqual(self.calls, ['flux'])

    def test_invalid_model_is_rejected_without_gpu_execution(self):
        self.assertEqual(self.request('arbitrary')[0], 422)
        self.assertEqual(self.calls, [])

    def test_browser_origin_is_rejected(self):
        self.assertEqual(self.request('flux', Origin='https://example.com')[0], 403)
        self.assertEqual(self.calls, [])

    def test_cancel_only_signals_named_active_job(self):
        first, second = threading.Event(), threading.Event()
        self.server.cancellations.update({'first': first, 'second': second})
        req = urllib.request.Request(self.url + '/v1/cancel', data=b'{"job_id":"first"}',
                                     headers={'Content-Type': 'application/json'})
        with self.opener.open(req) as response: self.assertEqual(response.status, 200)
        self.assertTrue(first.is_set())
        self.assertFalse(second.is_set())

    def test_early_cancel_prevents_job_from_starting(self):
        req = urllib.request.Request(self.url + '/v1/cancel', data=b'{"job_id":"early"}',
                                     headers={'Content-Type': 'application/json'})
        with self.opener.open(req) as response: self.assertEqual(response.status, 200)
        self.assertEqual(self.request('flux', job_id='early')[0], 503)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.request('flux', job_id='later')[0], 200)

    def test_cleanup_failure_does_not_report_success(self):
        process = Mock()
        process.poll.return_value = 0
        result = subprocess.CompletedProcess([], 1, b'', b'daemon unavailable')
        with patch.object(module.subprocess, 'run', return_value=result):
            with self.assertRaises(OSError): module.cleanup_job('owned-job', process)

    def test_cleanup_confirms_already_removed_worker(self):
        process = Mock()
        process.poll.return_value = 0
        missing = subprocess.CompletedProcess([], 1, b'', b'No such container')
        absent = subprocess.CompletedProcess([], 1, b'', b'No such object')
        with patch.object(module.subprocess, 'run', side_effect=[missing, missing, absent]), patch.object(module.time, 'sleep'):
            module.cleanup_job('owned-job', process)

    def test_cleanup_reads_newer_dockers_lowercase_answer(self):
        """Docker 29 on the Spark says `error: no such object`; the 4090's says `No such object`.
        Measured: the capitalised match failed a finished FLUX job with a 503."""
        process = Mock()
        process.poll.return_value = 0
        removed = subprocess.CompletedProcess([], 0, b'', b'Error response from daemon: No such container: owned-job')
        absent = subprocess.CompletedProcess([], 1, b'', b'error: no such object: owned-job')
        with patch.object(module.subprocess, 'run', side_effect=[removed, removed, absent]), patch.object(module.time, 'sleep'):
            module.cleanup_job('owned-job', process)

    def test_json_array_is_rejected(self):
        for route in ('/v1/image', '/v1/cancel'):
            req = urllib.request.Request(self.url + route, data=b'[]', headers={'Content-Type': 'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as raised: self.opener.open(req)
            self.assertEqual(raised.exception.code, 422)
            raised.exception.close()
        self.assertEqual(self.calls, [])

    def test_queue_full_is_bounded(self):
        self.server.busy.acquire()
        try: self.assertEqual(self.request('flux')[0], 503)
        finally: self.server.busy.release()
        self.assertEqual(self.request('flux')[0], 200)
        self.assertEqual(self.calls, ['flux'])

    def test_a_machine_without_the_legacy_3d_app_still_runs_jobs(self):
        """The Spark never had the 4090's display container. Until this test was added,
        `docker inspect` on it ran with check=True and every job answered 503."""
        root = Path(self.folder.name)
        job = root / 'media-extra/jobs/one'
        job.mkdir()
        (job / 'request.json').write_text('{}')
        handler = module.Handler.__new__(module.Handler)
        handler.server = Mock(root=root, kind='image')
        handler.disconnected = lambda: False
        worker = Mock(returncode=0)
        worker.poll.return_value = 0
        replies = iter([subprocess.CompletedProcess([], 1, b'', b'No such object: beyond-canvas-trellis2'),
                        subprocess.CompletedProcess([], 1, b'', b'No such container'),
                        subprocess.CompletedProcess([], 1, b'', b'No such container'),
                        subprocess.CompletedProcess([], 1, b'', b'No such object')])
        def fake_run(command, check=False, **_):
            reply = next(replies)
            if check and reply.returncode:
                raise subprocess.CalledProcessError(reply.returncode, command, reply.stdout, reply.stderr)
            return reply
        with patch.object(module.subprocess, 'run', side_effect=fake_run), \
                patch.object(module.subprocess, 'Popen', return_value=worker) as popen, \
                patch.object(module, 'gpu_busy', return_value=False), patch.object(module.time, 'sleep'):
            handler.generate(job, 'flux')
        popen.assert_called_once()

    def spark_job(self):
        """A handler and job folder, with Docker answering as a box without the legacy 3D app."""
        root = Path(self.folder.name)
        job = root / 'media-extra/jobs/one'
        job.mkdir()
        (job / 'request.json').write_text('{}')
        handler = module.Handler.__new__(module.Handler)
        handler.server = Mock(root=root, kind='image')
        handler.disconnected = lambda: False
        replies = iter([subprocess.CompletedProcess([], 1, b'', b'No such object: beyond-canvas-trellis2'),
                        subprocess.CompletedProcess([], 1, b'', b'No such container'),
                        subprocess.CompletedProcess([], 1, b'', b'No such container'),
                        subprocess.CompletedProcess([], 1, b'', b'No such object')])
        return handler, job, lambda command, **_: next(replies)

    def test_a_job_does_not_start_while_memory_is_below_the_floor(self):
        """Added for the Spark, whose chip draws on the machine's own memory:
        a job started with too little left freezes the node rather than failing."""
        handler, job, docker = self.spark_job()
        with patch.object(module.subprocess, 'run', side_effect=docker), \
                patch.object(module.subprocess, 'Popen') as popen, \
                patch.object(module, 'gpu_busy', return_value=False), \
                patch.object(module, 'memory_low', return_value=True), patch.object(module.time, 'sleep'):
            with self.assertRaises(OSError):
                handler.generate(job, 'flux')
        popen.assert_not_called()

    def test_a_running_job_is_stopped_when_memory_falls_below_the_floor(self):
        """Docker's --memory does not count the GB10 chip's memory (measured:
        a 4 GB-capped container held 8 GB on the chip), so the job is stopped from here."""
        handler, job, docker = self.spark_job()
        worker = Mock(returncode=None)
        worker.poll.return_value = None
        readings = iter([False, False, True])  # enough to start, fine at first, then low
        with patch.object(module.subprocess, 'run', side_effect=docker), \
                patch.object(module.subprocess, 'Popen', return_value=worker), \
                patch.object(module, 'gpu_busy', return_value=False), \
                patch.object(module, 'memory_low', side_effect=lambda: next(readings)), \
                patch.object(module.time, 'sleep'):
            with self.assertRaises(OSError) as raised:
                handler.generate(job, 'flux')
        self.assertIn('memory', str(raised.exception))
        worker.terminate.assert_called_once()

    def jobs(self):
        path = Path(self.folder.name) / 'media-extra/jobs.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def test_a_finished_job_leaves_one_line_and_none_of_the_request(self):
        """The Spark keeps a log of every job it ran and how long it took."""
        self.assertEqual(self.request('flux')[0], 200)
        [line] = self.jobs()
        self.assertEqual(set(line), {'at', 'kind', 'model', 'seconds', 'outcome', 'bytes'})
        self.assertEqual((line['kind'], line['model'], line['outcome']), ('image', 'flux', 'ok'))
        self.assertGreater(line['bytes'], 0)
        text = (Path(self.folder.name) / 'media-extra/jobs.jsonl').read_text()
        self.assertNotIn('data:image', text)
        self.assertNotIn('instruction', text)

    def test_a_job_folder_is_not_made_while_a_restart_holds_the_lock(self):
        """Code review: restart.sh counts job folders under this lock and stops the services
        before letting go, so a job that arrives meanwhile waits and is made after, never lost between."""
        lock = (Path(self.folder.name) / 'restart.lock').open('a+b')
        module.fcntl.flock(lock, module.fcntl.LOCK_EX)
        answered = []
        asking = threading.Thread(target=lambda: answered.append(self.request('flux')[0]), daemon=True)
        asking.start()
        asking.join(1.0)
        self.assertEqual((answered, self.calls), ([], []), 'a job started while a restart held the lock')
        module.fcntl.flock(lock, module.fcntl.LOCK_UN)
        lock.close()
        asking.join(10)
        self.assertEqual((answered, self.calls), ([200], ['flux']))

    def test_a_failed_job_is_recorded_as_failed(self):
        def broken(handler, job, model): raise OSError('worker failed')
        with patch.object(self.server.RequestHandlerClass, 'generate', broken):
            self.assertEqual(self.request('flux')[0], 503)
        [line] = self.jobs()
        self.assertEqual((line['model'], line['outcome'], line['bytes']), ('flux', 'failed', None))

    def test_a_request_refused_before_any_work_leaves_no_line(self):
        self.assertEqual(self.request('arbitrary')[0], 422)
        self.assertEqual(self.jobs(), [])


class Room(unittest.TestCase):
    def test_on_the_4090_a_job_waits_for_a_card_nobody_else_holds(self):
        with patch.object(module, 'gpu_busy', return_value=True):
            self.assertFalse(module.room_for('flux'))
        with patch.object(module, 'gpu_busy', return_value=False):
            self.assertTrue(module.room_for('flux'))

    def test_a_job_with_no_room_is_not_started(self):
        handler = module.Handler.__new__(module.Handler)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root / 'media-extra/jobs/job').mkdir(parents=True)
        handler.server = Mock(root=root, kind='image')
        handler.disconnected = lambda: False
        docker = lambda command, **_: subprocess.CompletedProcess([], 1, b'', b'No such object')
        with patch.object(module.subprocess, 'run', side_effect=docker), \
                patch.object(module.subprocess, 'Popen') as popen, \
                patch.object(module, 'gpu_busy', return_value=False), \
                patch.object(module, 'memory_low', return_value=False), \
                patch.object(module, 'room_for', return_value=False), patch.object(module.time, 'sleep'):
            with self.assertRaises(OSError) as raised:  # only room_for can refuse here
                handler.generate(root / 'media-extra/jobs/job', 'flux')
        self.assertIn('no room', str(raised.exception))
        popen.assert_not_called()


class SparkCommands(unittest.TestCase):
    def test_on_the_spark_trellis_keeps_its_models_in_place(self):
        """Moving TRELLIS.2's models off the chip hung a job queued behind a picture job."""
        path = Path(__file__).parents[2] / 'spark/media_spark.py'
        spec = importlib.util.spec_from_file_location('media_spark', path)
        spark = importlib.util.module_from_spec(spec)
        with patch('sys.path', [str(path.parent), *sys.path]):  # as when run as a script: memory_guard beside it
            spec.loader.exec_module(spark)
        for model, setting, image in (('trellis2', 'TRELLIS_LOW_VRAM=0', 'beyond-canvas/trellis2:dgx-spark'),):
            # A job in its own container: on the Spark itself the loaded model would otherwise take it.
            with patch.object(spark, 'trellis_ready', return_value=False):
                args = spark.command(Path('/root'), Path('/job'), model, 'worker')
            at = args.index(setting)
            self.assertEqual(args[at - 1], '-e')
            self.assertLess(at, args.index(image))  # an option only before the image

    def test_on_the_spark_a_job_runs_beside_other_work_when_its_memory_fits(self):
        """Run beside the other window's NVIDIA engine when there is
        room (operator). With that engine's 32 GB held, ~88 GiB are free: under the 115 GiB ceiling that is
        81 GiB of room, so 3D fits and a clip does not."""
        path = Path(__file__).parents[2] / 'spark/media_spark.py'
        spec = importlib.util.spec_from_file_location('media_spark_room', path)
        spark = importlib.util.module_from_spec(spec)
        with patch('sys.path', [str(path.parent), *sys.path]):
            spec.loader.exec_module(spark)
        # Nothing loaded and nothing stopped: run on the Spark itself, a real docker stop here once took
        # the class's loaded 3D model and first voice down, twice in one afternoon.
        stopped = []
        # The storybook's warm FLUX and voice too: this runs beside them on the node.
        loaded = (patch.object(spark, 'trellis_ready', return_value=False),
                  patch.object(spark, 'flux_warm', return_value=False),
                  patch.object(spark, 'voice_warm', return_value=False),
                  patch.object(spark, 'front_up', return_value=False),
                  # The safety reader never steps aside, so nothing asks whether it is up.
                  patch.object(spark.memory_guard, 'total_gib', return_value=121.69),
                  patch.object(spark.subprocess, 'run', side_effect=lambda argv, **_: stopped.append(argv)))
        for faked in loaded:
            faked.start()
            self.addCleanup(faked.stop)
        with patch.object(spark.memory_guard, 'available_gib', return_value=88.0):
            self.assertEqual([spark.room_for(m) for m in ('trellis2', 'wan2.2-i2v-a14b')],
                             [True, False])
            self.assertFalse(spark.room_for('a-model-nobody-measured'))  # counted as the largest
        with patch.object(spark.memory_guard, 'available_gib', return_value=120.0):
            self.assertTrue(spark.room_for('wan2.2-i2v-a14b'))
        self.assertEqual(stopped, [])

    def test_on_the_spark_flux_draws_only_a_storybooks_pages(self):
        """Operator decision: the FLUX still pose was retired because Wan makes the real
        animation. The 4B now draws a storybook's picture-book pages and nothing else: the
        book endpoint, with its own worker; still no single-picture endpoint, and the 9B stays unused."""
        path = Path(__file__).parents[2] / 'spark/media_spark.py'
        spec = importlib.util.spec_from_file_location('media_spark_no_picture', path)
        spark = importlib.util.module_from_spec(spec)
        with patch('sys.path', [str(path.parent), *sys.path]):
            spec.loader.exec_module(spark)
        self.assertNotIn('image', spark.media_server.MODELS)
        self.assertNotIn('mesh', spark.media_server.MODELS)  # Pixal3D, archived too
        self.assertEqual(spark.media_server.MODELS['video'], ('wan2.2-i2v-a14b',))
        self.assertEqual(spark.media_server.MODELS['book'], ('flux',))
        # Handed to the warm FLUX that the book's first job starts (tests/deploy/test_spark_flux_warm.py).
        book = spark.command(Path('/root'), Path('/job'), 'flux', 'worker')
        self.assertEqual(book[1:], [str(path.parent / 'flux_client.py'), '/job'])
        for model in ('flux-9b', 'pixal'):
            with self.assertRaises(ValueError):
                spark.command(Path('/root'), Path('/job'), model, 'worker')



class BookContracts(unittest.TestCase):
    """A storybook's pages in a picture-book style: several pictures in one job, so the Spark loads
    FLUX once, and one JSON answer holding every page in order."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        (root / 'media-extra/jobs').mkdir(parents=True)
        (root / 'media-extra/flux.ready').touch()
        self.jobs, self.drawn = [], None
        test = self
        class Fake(module.Handler):
            def generate(self, job, model):
                asked = json.loads((job / 'request.json').read_text())['pictures']
                test.jobs.append((model, len(asked), (job / 'input.png').exists()))
                count = len(asked) if test.drawn is None else test.drawn
                pictures = [base64.b64encode(b'\xff\xd8\xff' + b'jpeg' * 20).decode() for _ in range(count)]
                (job / 'output.json').write_text(json.dumps({'pictures': pictures}))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Fake)
        self.server.pending_cancels = {}
        self.server.cancellations, self.server.cancel_lock = {}, threading.Lock()
        self.server.root, self.server.kind, self.server.busy = root, 'book', threading.Lock()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    @staticmethod
    def page(**changes):
        return {'image': 'data:image/jpeg;base64,' + base64.b64encode(b'x' * 256).decode(),
                'instruction': 'Repaint as watercolour', 'seed': 42, **changes}

    def post(self, pictures):
        req = urllib.request.Request(self.url + '/v1/pictures', data=json.dumps({'model': 'flux', 'pictures': pictures}).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with self.opener.open(req) as response:
                return response.status, response.headers.get('Content-Type'), response.read()
        except urllib.error.HTTPError as error:
            with error: return error.code, None, error.read()

    def test_every_page_of_the_job_comes_back_in_one_answer(self):
        status, mime, body = self.post([self.page(), self.page(seed=43), self.page()])
        self.assertEqual((status, mime), (200, 'application/json'))
        self.assertEqual(len(json.loads(body)['pictures']), 3)
        self.assertEqual(self.jobs, [('flux', 3, False)], 'one job for the three, and no single input picture')

    def test_a_job_past_eight_pages_or_with_a_bad_page_never_reaches_the_chip(self):
        for pictures in ([self.page()] * 9, [], [self.page(instruction='')], [self.page(seed=True)],
                         [self.page(image='https://example.com/a.png')], [self.page(seed=2 ** 31)]):
            self.assertEqual(self.post(pictures)[0], 422, pictures[:1])
        self.assertEqual(self.jobs, [])

    def test_an_answer_short_of_a_page_is_not_passed_on(self):
        self.drawn = 2
        self.assertEqual(self.post([self.page()] * 3)[0], 503)

    def test_no_page_instruction_or_picture_reaches_the_workers_log(self):
        root = Path(self.folder.name)
        job = root / 'media-extra/jobs/one'
        job.mkdir()
        secret = 'Keep the blonde princess on the left tower'
        (job / 'request.json').write_text(json.dumps({'pictures': [self.page(instruction=secret)]}))
        handler = module.Handler.__new__(module.Handler)
        handler.server = Mock(root=root, kind='book')
        handler.disconnected = lambda: False
        worker = Mock(returncode=0)
        worker.poll.return_value = 0
        def started(command, stdout, stderr):
            stdout.write(('echoed: ' + secret).encode())
            return worker
        replies = iter([subprocess.CompletedProcess([], 1, b'', b'No such object: beyond-canvas-trellis2'),
                        subprocess.CompletedProcess([], 1, b'', b'No such container'),
                        subprocess.CompletedProcess([], 1, b'', b'No such container'),
                        subprocess.CompletedProcess([], 1, b'', b'No such object')])
        with patch.object(module.subprocess, 'run', side_effect=lambda command, **_: next(replies)), \
                patch.object(module.subprocess, 'Popen', side_effect=started), \
                patch.object(module, 'gpu_busy', return_value=False), patch.object(module.time, 'sleep'):
            handler.generate(job, 'flux')
        kept = (root / 'media-extra/flux-last.log').read_text()
        self.assertNotIn(secret, kept)
        self.assertIn('[request content omitted]', kept)


class ChildVoiceContracts(unittest.TestCase):
    """A storybook page read in a child's copied voice on the Spark: the page and the first answer the
    child said out loud about its drawing go in one job, and the recording never reaches the worker's log."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        (root / 'media-extra/jobs').mkdir(parents=True)
        (root / 'media-extra/VoxCPM2.ready').touch()
        self.jobs = []
        test = self
        class Fake(module.Handler):
            def generate(self, job, model):
                test.jobs.append((model, json.loads((job / 'request.json').read_text())['voice']))
                (job / 'output.wav').write_bytes(b'RIFF' + b'\0' * 4 + b'WAVE' + b'\0' * 64)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Fake)
        self.server.pending_cancels = {}
        self.server.cancellations, self.server.cancel_lock = {}, threading.Lock()
        self.server.root, self.server.kind, self.server.busy = root, 'voice', threading.Lock()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    def post(self, **body):
        asked = {'model': 'VoxCPM2', 'voice': 'child', 'input': 'The fish swim home.',
                 'reference': base64.b64encode(b'RIFF' + b'\1' * 4096).decode(), **body}
        req = urllib.request.Request(self.url + '/v1/audio/speech', data=json.dumps(asked).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with self.opener.open(req) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            with error: return error.code, error.read()

    def test_a_page_and_its_childs_recording_make_one_job(self):
        status, body = self.post()
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b'RIFF'))
        self.assertEqual(self.jobs, [('VoxCPM2', 'child')])

    def test_a_childs_voice_without_a_recording_never_reaches_the_chip(self):
        self.assertEqual(self.post(reference_text='x' * 1001)[0], 422)
        for reference in ('', 'not base64!', base64.b64encode(b'ID3' + b'x' * 4096).decode(),
                          base64.b64encode(b'RIFF').decode(), base64.b64encode(b'RIFF' + b'x' * (3 * 1024 * 1024)).decode()):
            self.assertEqual(self.post(reference=reference)[0], 422)
        self.assertEqual(self.jobs, [])

    def test_the_recording_never_reaches_the_workers_log(self):
        root = Path(self.folder.name)
        job = root / 'media-extra/jobs/one'
        job.mkdir()
        recording = base64.b64encode(b'RIFF-a-childs-voice' * 64).decode()
        words = 'They want to go back to their own home'
        (job / 'request.json').write_text(json.dumps({'voice': 'child', 'input': 'The fish swim home.', 'reference': recording,
                                                      'reference_text': words}))
        handler = module.Handler.__new__(module.Handler)
        handler.server = Mock(root=root, kind='voice')
        handler.disconnected = lambda: False
        worker = Mock(returncode=0)
        worker.poll.return_value = 0
        def started(command, stdout, stderr):
            stdout.write(('echoed: ' + recording + ' ' + words).encode())
            return worker
        def docker(command, **_):   # nothing is running and nothing is left behind
            return subprocess.CompletedProcess([], 1, b'', b'No such container' if command[1] == 'rm' else b'No such object')
        with patch.object(module.subprocess, 'run', side_effect=docker), \
                patch.object(module.subprocess, 'Popen', side_effect=started), \
                patch.object(module, 'gpu_busy', return_value=False), patch.object(module.time, 'sleep'):
            handler.generate(job, 'VoxCPM2')
        kept = (root / 'media-extra/VoxCPM2-last.log').read_text()
        self.assertNotIn(recording, kept)
        self.assertNotIn(words, kept, "nor the child's words heard in it")
        self.assertIn('[request content omitted]', kept)


if __name__ == '__main__': unittest.main()
