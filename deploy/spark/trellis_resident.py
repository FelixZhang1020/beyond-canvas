"""TRELLIS.2 kept loaded on the Spark: one process, many 3D models.

Operator decision: loading the model is about 40% of a 3D job, and the sketch entrance
is the one place a child waits with nothing to look at. This process loads once
(trellis_worker.load) and builds each model with the same code a one-off job uses
(trellis_worker.build), with the same seed and settings, so the same drawing still gives the same
model. It holds the weights between jobs; a clip, which needs that memory, pauses it
(media_spark.room_for) and it loads again afterwards.

It listens on the Unix socket /resident/trellis.sock, created only once the model is loaded, so its
presence means ready. One connection is one model: the client (trellis_client.py) sends the job
folder's name and a newline; the folder is looked up under /jobs, and the answer is `ok` or
`error <kind>`. The child's drawing stays in the job folder and is never echoed back. Runs in the
TRELLIS.2 container, started by trellis-resident.sh.
"""
import os
import socketserver
import sys
from pathlib import Path

SOCKET = Path('/resident/trellis.sock')
JOBS = Path('/jobs')


def serve(build, socket_path=SOCKET, jobs=JOBS, after_failure=lambda: os._exit(1)):
    """Answer one model per connection with build(job_folder), until the process is stopped.

    A job that fails ends the process once the answer is sent: an error on the chip can leave the
    model unusable while the socket still accepts, and every later job would fail too (the picture
    model found this out first). trellis-resident.sh starts a fresh one; jobs meanwhile go to
    a one-off container, as they did before this existed.
    """
    root = Path(jobs).resolve()

    class Model(socketserver.StreamRequestHandler):
        def handle(self):
            name = self.rfile.readline(256).decode('utf-8', 'replace').strip()
            if not name:   # media_spark.trellis_ready connecting to see whether we answer
                return
            job = (root / name).resolve()
            if job.parent != root or not (job / 'input.png').is_file():
                self.wfile.write(b'error bad-job\n')
                return
            try:
                build(job)
            except Exception as error:
                self.wfile.write(f'error {type(error).__name__}\n'.encode())
                self.wfile.flush()
                after_failure()
                return
            self.wfile.write(b'ok\n')

    socket_path = Path(socket_path)
    socket_path.unlink(missing_ok=True)
    with socketserver.UnixStreamServer(str(socket_path), Model) as server:
        os.chmod(socket_path, 0o600)
        print('TRELLIS.2 loaded; answering on', socket_path, flush=True)
        server.serve_forever()


if __name__ == '__main__':
    sys.path.insert(0, '/runner')
    import trellis_worker  # noqa: E402  (torch and TRELLIS.2 load here, inside the container)
    pipeline = trellis_worker.load()
    serve(lambda job: trellis_worker.build(pipeline, str(job)))
