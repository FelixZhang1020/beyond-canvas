"""Hand one storybook page to the warm VoxCPM2 (voice_book_worker.py), starting it when none answers.

The media service runs this for every voice job on the Spark (media_spark.command), as flux_client.py does for a
book's pictures, whose starting and handing over this reuses. The first page of a book starts the warm container
and waits for it to load; later pages find it answering. Exit 0 once output.wav is written. Standard library only.
usage: voice_client.py JOB_FOLDER
"""
import functools
import os
import sys
from pathlib import Path

import flux_client as warm

NAME = 'beyond-canvas-voice-warm'
IMAGE = 'beyond-canvas/voice:1'
IDLE_S = 600


def socket_path(resident=None):
    return (resident or warm.RESIDENT) / 'voice-book.sock'


def start_command(idle_s=IDLE_S):
    """The warm container: the voice job's weights, the job folders and the socket folder, as our own user."""
    home = warm.HOME
    return ['docker', 'run', '-d', '--rm', '--name', NAME, '--gpus', 'all', '--shm-size', '8g',
            '-u', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp', '-e', 'NUMBA_CACHE_DIR=/tmp/numba',
            '-e', 'HF_HUB_OFFLINE=1', '-e', 'TRANSFORMERS_OFFLINE=1', '-e', 'PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True',
            '-v', f'{home}/models/voxcpm2:/models/voice:ro', '-v', f'{home}/beyond-canvas/deploy/spark:/spark:ro',
            '-v', f'{home}/spark-media/media-extra/jobs:/jobs', '-v', f'{warm.RESIDENT}:/resident',
            '--entrypoint', 'python', IMAGE, '/spark/voice_book_worker.py', '--idle', str(idle_s)]


def main(job):
    path = socket_path()
    begin = functools.partial(warm.start, name=NAME, command=start_command(), ready=lambda: warm.answers(path))
    return warm.main(Path(job), path=path, timeout_s=300, begin=begin, output='output.wav')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main(sys.argv[1]))
