"""The 4090's media server, pointed at the Spark's containers.

`deploy/gpu-media/extra/media_server.py` already does everything a media
endpoint needs: one job at a time, cancellation by job id, the shared GPU lock,
a disposable container per job so its memory is freed, output checks and a
receipt of the last generation. The one part that belongs to the 4090 is which
container runs which model from which folder, so that function is replaced here
and nothing else is copied.

The Spark also runs a model the 4090 cannot hold, Wan 2.2 I2V A14B, so the
video endpoint answers for it instead of the 5B.

The FLUX still pose was retired (operator: Wan makes the real animation); its picture
worker, the kept-loaded FLUX and its pause are in the repository's history. FLUX.2 Klein 4B came back
later for one job only, the storybook's picture-book pages (--kind book, flux_book_worker.py):
a batch per job, handed to a warm FLUX that a book's first job starts and that leaves ~3 minutes after the
book's last (flux_client.py; operator). VoxCPM2 reads a storybook page in a child's copied voice
(--kind voice, voice_book_worker.py; operator), kept warm the same way (voice_client.py). No second 3D
endpoint either since the still pose was retired: Pixal3D was archived; its weights in ~/pixal3d and its
container stay, unused.

Run on the node with the system python3 (stdlib only), as start.sh does:
    python3 deploy/spark/media_spark.py --kind video --root ~/spark-media --port 7260
    python3 deploy/spark/media_spark.py --kind book --root ~/spark-media --port 7270
    python3 deploy/spark/media_spark.py --kind voice --root ~/spark-media --port 7280
"""
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNERS = HERE.parent / 'gpu-media' / 'extra'
sys.path.insert(0, str(RUNNERS))
import media_server  # noqa: E402
import memory_guard  # noqa: E402  (beside this file)

IMAGE = 'beyond-canvas/spark-diffusers:1'
WEIGHTS = Path.home() / 'models'
# TRELLIS.2's Hugging Face cache and runtime/, laid out by weights_manifest.py and
# `deploy/trellis2/sync-weights.sh ~/trellis prepare`.
TRELLIS = Path.home() / 'trellis' / 'models'
DEPLOY = HERE.parent


def command(root, job, model, name):
    """The docker command for one job, the Spark's counterpart of media_server.command."""
    # HF_MODULES_CACHE as on the 4090: RMBG-2.0 is remote code that transformers
    # writes into a modules folder on load, and /models is mounted read-only. Left
    # out at first, TRELLIS.2's first Spark job failed on it.
    base = ['docker', 'run', '--rm', '--name', name, '--gpus', 'all', '--shm-size', '16g',
            '-e', 'HF_HUB_OFFLINE=1', '-e', 'TRANSFORMERS_OFFLINE=1', '-e', 'HF_MODULES_CACHE=/tmp/hf-modules',
            '-e', 'PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True', '-v', f'{job}:/job']
    if model == 'wan2.2-i2v-a14b':
        return base + ['-v', f'{WEIGHTS}/wan2.2-i2v-a14b-diffusers:/models/wan:ro', '-v', f'{HERE}:/spark:ro',
                       '--entrypoint', 'python', IMAGE, '/spark/wan_i2v_worker.py']
    if model == 'flux':   # a storybook's pages: handed to the warm FLUX, started by the book's first job
        return [sys.executable, str(HERE / 'flux_client.py'), str(job)]
    if model == 'VoxCPM2':   # a storybook page in a child's voice: handed to the warm VoxCPM2 the same way
        return [sys.executable, str(HERE / 'voice_client.py'), str(job)]
    # The 3D route runs the 4090's own worker, mounts and patch, over the Spark's
    # container (deploy/spark/build-3d.sh).
    # TRELLIS_LOW_VRAM=0 keeps its models in place: moving them between the chip's side and
    # the CPU's saves nothing on one shared memory, and hung behind a picture job (the worker says more).
    if model == 'trellis2' and trellis_ready():   # already loaded: hand it the job (trellis_client.py)
        return [sys.executable, str(HERE / 'trellis_client.py'), str(job)]
    if model == 'trellis2':
        return base + ['-e', 'TRELLIS_LOW_VRAM=0',
                       '-e', 'ATTN_BACKEND=flash_attn', '-e', 'SPARSE_ATTN_BACKEND=flash_attn',
                       '-e', 'HF_HOME=/models/huggingface', '-v', f'{TRELLIS}:/models:ro',
                       '-v', f'{DEPLOY}/trellis2/patches/image_feature_extractor.py'
                             ':/app/trellis2/modules/image_feature_extractor.py:ro',
                       '-v', f'{RUNNERS}:/runner:ro', '--entrypoint', 'python',
                       'beyond-canvas/trellis2:dgx-spark', '/runner/trellis_worker.py']
    raise ValueError(f'{model} is not installed on the Spark')


def memory_low():
    """Below memory_guard's floor, a job is refused before it starts and stopped while it runs.

    The GB10's chip allocates from the machine's own memory, which is why running out
    freezes the node instead of failing one process. Docker's --memory cannot stop
    that: as measured, a container capped at 4 GB held 8 GB on the chip and
    was never killed, while MemAvailable fell by 17 GiB for 16 GiB taken on the chip.
    So the available-memory figure is watched from here, as the builds' guard watches it.
    """
    return memory_guard.available_gib() < memory_guard.FLOOR_GIB


# The most memory each job holds at its peak, in GiB, measured on the Spark from the recorder
# (~/logs/ram-measure.log, the first timing runs and the first clip), rounded up.
PEAK_GIB = {'trellis2': 38, 'wan2.2-i2v-a14b': 85, 'flux': 22,   # flux: 22 held when the 4B was kept loaded
            'VoxCPM2': 12}   # measured on the node: docs/measured/child-voice.md
# A storybook's FLUX stays loaded ~3 minutes after the book's last job (flux_book_worker.py, operator),
# holding the 22 GiB counted above; a job on it adds little, and any other job sends it away first.
# Measured by the node's monitor on one book: ~2 GiB on its first job, no more on the next three. Counted at 4,
# it paused the safety reader for every book job at the ~27 GiB a loaded FLUX leaves, and each check then
# waited ~23 s for it to load again (docs/measured/storybook-check-and-speed.md; operator's go to count 2).
FLUX_WARM_NAME = 'beyond-canvas-flux-warm'
FLUX_JOB_GIB = 2
# A storybook's VoxCPM2 stays loaded ten minutes after the book's last page (voice_book_worker.py), holding the
# GiB counted in PEAK_GIB; like the FLUX, any other job sends it away first and the next page starts it again.
VOICE_WARM_NAME = 'beyond-canvas-voice-warm'
VOICE_JOB_GIB = 2
WARM_MODELS = ('flux', 'VoxCPM2')


def answering(sock):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(2)
            probe.connect(str(RESIDENT / sock))
        return True
    except OSError:
        return False


def flux_warm():
    """Whether the storybook's FLUX is loaded and answering (its socket accepts)."""
    return answering('flux-book.sock')


def voice_warm():
    """Whether the storybook's VoxCPM2 is loaded and answering."""
    return answering('voice-book.sock')


def warm_models():
    """The storybook's warm models by the model a job names: (container, whether it answers now)."""
    return {'flux': (FLUX_WARM_NAME, flux_warm), 'VoxCPM2': (VOICE_WARM_NAME, voice_warm)}

# NVIDIA's safety reader, kept loaded by safety-reader.sh for the class's second look: the one model
# the Spark keeps loaded between jobs. A job that does not fit beside it pauses it (the clip's ~85 GiB
# does not fit beside its ~11), and it loads again after the job.
RESIDENT = Path.home() / 'spark-media' / 'resident'
READER_NAME = 'nemotron-safety'
READER_GIB = 11


def reader_up():
    """Whether the safety reader's container is running."""
    try:
        found = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', READER_NAME],
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return found.stdout.strip() == 'true'


# TRELLIS.2 kept loaded between 3D jobs (trellis_resident.py, kept running by trellis-resident.sh).
# Measured on the node, the same sketch each time: 205.7 s in its own container, 124.6 s on the
# first job after a load, 67-70 s on every job after that. It holds ~26 GiB when it loads and ~31 once it
# has worked. A job on top of those weights took 1.6 GiB, and ~5 GiB the first time after a load; 8 leaves
# room for a bigger drawing without pretending a job is free.
TRELLIS_RESIDENT_NAME = 'beyond-canvas-trellis-resident'
TRELLIS_JOB_GIB = 8


# Qwen3.6, the class's first voice, kept loaded by qwen-front.sh (operator). It holds ~50 GiB
# and cannot run smaller (docs/measured/chat-speed-and-front-voice.md), so it never fits beside a
# clip; while it is paused the class's chat is written by Step 3.7 Flash, as it was before.
FRONT_NAME = 'qwen-front'


def front_up():
    """Whether the first voice's container is running."""
    try:
        found = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', FRONT_NAME],
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return found.stdout.strip() == 'true'


def trellis_ready():
    """Whether the 3D model is loaded and answering (its socket accepts)."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(2)
            probe.connect(str(RESIDENT / 'trellis.sock'))
        return True
    except OSError:
        return False


def peak_of(model):
    if model == 'trellis2' and trellis_ready():
        return TRELLIS_JOB_GIB
    if model == 'flux' and flux_warm():
        return FLUX_JOB_GIB
    if model == 'VoxCPM2' and voice_warm():
        return VOICE_JOB_GIB
    return PEAK_GIB.get(model, max(PEAK_GIB.values()))


def fits(model):
    return memory_guard.available_gib() - peak_of(model) >= memory_guard.FLOOR_GIB


def room_for(model):
    """Enough free memory for this model's peak above memory_guard's floor.

    Operator decision: class jobs run beside another window's work on the chip (its
    NVIDIA model engine held 32 GB when this was decided) when there is room, instead of refusing whenever
    anything else is there, which the 4090's rule does. A model never measured counts as the
    largest. A job that started with room is still stopped if memory later falls below the floor.

    A job that does not fit only because the safety reader holds its ~11 GiB pauses the reader and it
    loads again after the job (SparkHandler); one that would not fit without it either leaves it be.
    While it is paused a look stops nothing and is recorded as unavailable. Called by the media service
    after it holds the GPU lock, so the reader is not loading at that moment.
    """
    if fits(model):
        return True
    # The storybook's warm FLUX and voice before anything: each is kept only to save the next page's load. No
    # flag, as nothing keeps them: the book's next job starts them again.
    for other, (container, up) in warm_models().items():
        if model != other and up():
            subprocess.run(['docker', 'rm', '-f', container], capture_output=True, timeout=60)
            if _settled(model):
                return True
    # The loaded 3D model goes first: giving its memory back costs a load, while the reader's absence
    # costs a class its second safety look. A 3D job never asks the loaded model it is about to use.
    if model != 'trellis2' and trellis_ready() and _step_aside('trellis-paused', TRELLIS_RESIDENT_NAME, model):
        return True
    # The first voice next: while it is away chat falls back to Step 3.7 Flash, slower but whole, and it
    # loads again in about four minutes. The reader goes last because its absence costs a safety look.
    # Never for a book's pictures or its child's voice: the teacher is talking meanwhile, and the chat would fall
    # back to Step for four minutes for a job of one. Beside the 3D model's room they fit (22 GiB).
    if model not in WARM_MODELS and front_up() and _step_aside('front-paused', FRONT_NAME, model):
        return True
    peak = peak_of(model)
    if not reader_up() or memory_guard.available_gib() + READER_GIB - peak < memory_guard.FLOOR_GIB:
        return False
    return _step_aside('paused', READER_NAME, model)


def _step_aside(flag, container, model):
    """Stop one kept-loaded model and wait for its memory; the flag keeps it down until the job lifts it.

    The wait ends when the job fits or when the freed memory has stopped growing. What a model gives back
    is not what it was thought to hold: at the first clip beside the first voice the 3D
    model freed far less than the 31 GiB counted for it, and a fixed 30 s wait for memory that could not
    come held the GPU lock before the next model was asked.
    """
    RESIDENT.mkdir(parents=True, exist_ok=True)
    (RESIDENT / flag).write_text(str(os.getpid()))
    # Both serve from python as the container's first process, which ignores a polite stop.
    subprocess.run(['docker', 'stop', '-t', '2', container], capture_output=True, timeout=60)
    return _settled(model)


def _settled(model):
    """Whether the job fits once the memory just given back has shown up (see _step_aside)."""
    best, still = memory_guard.available_gib(), 0
    for _ in range(30):   # the freed memory shows in MemAvailable within seconds
        if fits(model):
            return True
        time.sleep(1)
        now = memory_guard.available_gib()
        best, still = (now, 0) if now >= best + 1 else (best, still + 1)
        if still >= 3:
            return fits(model)
    return False


def resume_reader():
    """Let safety-reader.sh load the reader again, if this service paused it."""
    _lift('paused')


def resume_front():
    """Let qwen-front.sh load the first voice again, if this service paused it."""
    _lift('front-paused')


def resume_resident():
    """Let trellis-resident.sh load the 3D model again, if this service paused it."""
    _lift('trellis-paused')


def _lift(flag):
    flag = RESIDENT / flag
    try:
        if flag.read_text().strip() == str(os.getpid()):
            flag.unlink()
    except OSError:
        pass


def once_more_without_the_resident(attempt, model, disconnected, before_retry=lambda: None):
    """Run a 3D job; if the kept-loaded model went away under it, run it once more in a container of its own.

    Measured on the node: a pause left behind by a restarted service stopped the loaded model
    while a job was running, and the child's 3D model was lost with it. The loaded model can also stop for
    a clip or exit after a failed job. A job that failed on its own fails the same way twice, so only a
    model that has gone away earns the second attempt, and a teacher who walked away gets none.
    """
    used = model == 'trellis2' and trellis_ready()
    try:
        return attempt()
    except OSError:
        if not used or trellis_ready() or disconnected():
            raise
        before_retry()
        return attempt()


def _handed_to_the_resident(process):
    """Whether this job went to the loaded model instead of a container of its own."""
    return any('trellis_client.py' in str(word) for word in (getattr(process, 'args', None) or ()))


def cleanup_job(name, process):
    """media_server's cleanup, and the loaded model too when the job it is running is being stopped.

    media_server stops the worker it started and removes the container it named. For a job handed to
    the loaded model those are a socket client and a container that was never created: the building
    happens inside trellis-resident, which neither of them names. Closing the socket tells it nothing.
    That used to leave a cancelled, timed-out or memory-stopped job still generating after the
    GPU lock was released and the job folder deleted, so later media work overlapped it -- and the
    memory floor, which exists because this node freezes rather than failing one process when memory
    runs out, could no longer stop the work that was eating the memory.

    Only a job being stopped mid-run takes the loaded model down with it: if the worker has already
    exited, the job finished and the model stays loaded, which is the whole point of keeping it. The
    flag written here is the one _step_aside uses, so resume_resident lifts it afterwards and
    trellis-resident.sh loads the model again.
    """
    stopping = process is not None and process.poll() is None and _handed_to_the_resident(process)
    # A storybook job stopped mid-run takes its warm FLUX or voice with it, for the same reason; the next starts it.
    running = process is not None and process.poll() is None
    words = [str(word) for word in (getattr(process, 'args', None) or ())]
    warm = [c for script, c in (('flux_client.py', FLUX_WARM_NAME), ('voice_client.py', VOICE_WARM_NAME))
            if running and any(script in word for word in words)]
    try:
        _media_server_cleanup_job(name, process)
    finally:
        for container in warm:
            subprocess.run(['docker', 'rm', '-f', container], capture_output=True, timeout=60)
        if stopping:
            RESIDENT.mkdir(parents=True, exist_ok=True)
            (RESIDENT / 'trellis-paused').write_text(str(os.getpid()))
            # As _step_aside does: python is the container's first process and ignores a polite stop.
            subprocess.run(['docker', 'stop', '-t', '2', TRELLIS_RESIDENT_NAME], capture_output=True, timeout=60)


def waiting_flag():
    """This job's note that it wants the GPU lock, which the keepers read before reloading (keeper-common.sh)."""
    return RESIDENT / f'waiting-{os.getpid()}-{threading.get_ident()}'


class SparkHandler(media_server.Handler):
    def generate(self, job, model):
        waiting = waiting_flag()
        RESIDENT.mkdir(parents=True, exist_ok=True)
        waiting.write_text(str(os.getpid()))

        def attempt():
            # super, not media_server.Handler: this file replaces that name with this class below, so
            # calling it by name calls this method again, for ever (every job failed when it did).
            return super(SparkHandler, self).generate(job, model)
        try:
            return once_more_without_the_resident(attempt, model, self.disconnected,
                                                  lambda: (job / 'output.glb').unlink(missing_ok=True))
        finally:
            waiting.unlink(missing_ok=True)
            resume_reader()      # the lock is released by now; each reload takes it again
            resume_resident()
            resume_front()


media_server.command = command
media_server.memory_low = memory_low
media_server.room_for = room_for
# Captured before the override, and called by ours: the name is what media_server's own generate()
# reaches for in its finally, so replacing it here is what puts the loaded model into that cleanup.
_media_server_cleanup_job = media_server.cleanup_job
media_server.cleanup_job = cleanup_job
media_server.Handler = SparkHandler
# No 'image' kind since the still pose was retired, and no 'mesh' kind (Pixal3D) since it was archived.
# 'book' is FLUX again, for the storybook's picture-book pages only.
media_server.MODELS = {**{k: v for k, v in media_server.MODELS.items() if k not in ('image', 'mesh')},
                       'video': ('wan2.2-i2v-a14b',)}

if __name__ == '__main__':
    media_server.main()
