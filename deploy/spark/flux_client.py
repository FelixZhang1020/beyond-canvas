"""Hand one storybook picture job to the warm FLUX.2 Klein (flux_book_worker.py), starting it when none answers.

The media service runs this for every 'book' job (media_spark.command), so its lock, memory floor, cancellation
and output checks stay exactly as they are. The first job of a book starts the warm container and waits for it to
load; later ones find it answering. Exit 0 once output.json is written. Standard library only.
usage: flux_client.py JOB_FOLDER
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
RESIDENT = HOME / 'spark-media' / 'resident'
NAME = 'beyond-canvas-flux-warm'
IMAGE = 'beyond-canvas/spark-diffusers:1'
IDLE_S = 180
LOAD_S = 180   # measured 13.6-23.8 s; a slow disk or a busy chip gets the rest


def socket_path(resident=None):
    return (resident or RESIDENT) / 'flux-book.sock'


def answers(path=None):
    """Whether the warm model is loaded and taking jobs (its socket accepts)."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(2)
            probe.connect(str(path or socket_path()))
        return True
    except OSError:
        return False


def start_command(idle_s=IDLE_S):
    """The warm container: the book job's mounts and settings, plus the job folders and the socket folder, as our
    own user so the socket and the pages it writes are ours (as trellis-resident-load.sh runs the 3D model)."""
    return ['docker', 'run', '-d', '--rm', '--name', NAME, '--gpus', 'all', '--shm-size', '16g',
            '-u', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp',
            '-e', 'HF_HUB_OFFLINE=1', '-e', 'TRANSFORMERS_OFFLINE=1', '-e', 'PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True',
            '-v', f'{HOME}/models/flux2-klein-4b:/models/flux:ro', '-v', f'{HOME}/beyond-canvas/deploy/spark:/spark:ro',
            '-v', f'{HOME}/spark-media/media-extra/jobs:/jobs', '-v', f'{RESIDENT}:/resident',
            '--entrypoint', 'python', IMAGE, '/spark/flux_book_worker.py', '--idle', str(idle_s)]


def start(run=subprocess.run, ready=answers, sleep=time.sleep, load_s=LOAD_S, name=NAME, command=None):
    """Start the warm container and wait until it answers; False if it did not start or never loaded.

    `name` and `command` let the storybook's voice (voice_client.py) start its own warm model the same way.
    """
    run(['docker', 'rm', '-f', name], capture_output=True, timeout=60)   # one that stopped answering
    RESIDENT.mkdir(parents=True, exist_ok=True)
    if run(command or start_command(), capture_output=True, timeout=60).returncode:
        return False
    deadline = time.monotonic() + load_s
    while not ready():
        if time.monotonic() > deadline:
            run(['docker', 'rm', '-f', name], capture_output=True, timeout=60)
            return False
        sleep(0.5)
    return True


def main(job, path=None, timeout_s=900, begin=start, ready=answers, output='output.json'):
    """Hand the job over and wait for its answer; 0 once `output` is written (voice_client.py's is output.wav)."""
    job = Path(job)
    if not ready(path) and not begin():
        print('the warm picture model did not start', flush=True)
        return 1
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout_s)
        connection.connect(str(path or socket_path()))
        connection.sendall(job.name.encode() + b'\n')
        answer = connection.makefile('rb').readline().decode('utf-8', 'replace').strip()
    print(answer or 'no answer', flush=True)
    return 0 if answer == 'ok' and (job / output).is_file() else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
