"""How long a Wan 2.2 clip can be, and what each length costs: one drawing, several lengths, timed.

Operator: "i want expand to 10s, test different seconds generation time". The class makes
49 pictures (~3 s at 16 fps). Wan 2.2 was trained on 81 (5 s); anything longer is past what it was
taught, which is part of what this trial is for.

Runs ON the node, from its own copy of the code (never ~/beyond-canvas), and goes through the media
service's own job path: the GPU lock the class's clip service takes, the keepers stepping aside, the
memory floor that stops a worker before the node can freeze, and a job folder restart.sh counts. Only
the job deadline is raised, in this process alone, because a 10 s clip cannot finish inside the
class's 20 minutes. The keepers stay aside for the whole trial rather than reloading between lengths.

    python3 deploy/spark/clip_length_trial.py DRAWING OUT_DIR 49 81 113 161
"""
import ast
import fcntl
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import media_spark  # noqa: E402  (patches media_server with the Spark's command, room and cleanup)

media_server = media_spark.media_server
ROOT = Path.home() / 'spark-media'
MODEL = 'wan2.2-i2v-a14b'
ACTION = "The river flows gently past the snowy banks, and a little snow drifts down."


def class_instruction(action):
    """The words a class clip is sent with (studio/making/animation.py), read without importing the studio."""
    tree = ast.parse((HERE.parents[1] / 'studio' / 'animation.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'VIDEO_PROMPT':
            return ast.literal_eval(node.value) + json.dumps(action, ensure_ascii=False)
    raise SystemExit('VIDEO_PROMPT not found in studio/making/animation.py')


def handler():
    job_handler = object.__new__(media_spark.SparkHandler)
    job_handler.server = SimpleNamespace(root=ROOT, kind='video', phase=None, active_model=None)
    job_handler.disconnected = lambda: False
    return job_handler


def lowest_memory(stop, seen):
    while not stop.is_set():
        seen.append(media_spark.memory_guard.available_gib())
        time.sleep(1)


def one_clip(drawing, instruction, frames, out):
    with (ROOT / 'restart.lock').open('a+b') as gate:
        fcntl.flock(gate, fcntl.LOCK_SH)
        made = tempfile.TemporaryDirectory(prefix='media-trial-', dir=ROOT / 'media-extra' / 'jobs')
    with made as folder:
        job = Path(folder)
        (job / 'request.json').write_text(json.dumps({'instruction': instruction, 'frames': frames, 'seed': 42}))
        shutil.copyfile(drawing, job / 'input.png')   # PIL reads the picture by its content, not its name
        stop, seen = threading.Event(), []
        watcher = threading.Thread(target=lowest_memory, args=(stop, seen), daemon=True)
        started = time.monotonic()
        watcher.start()
        outcome = 'ok'
        try:
            handler().generate(job, MODEL)
            shutil.copyfile(job / 'output.mp4', out / f'clip-{frames}.mp4')
        except Exception as error:   # a failed length is a result, and the next one still runs
            outcome = f'failed: {error}'
        finally:
            stop.set()
            watcher.join()
            if (job / 'worker.log').is_file():
                shutil.copyfile(job / 'worker.log', out / f'worker-{frames}.log')
    return {'frames': frames, 'seconds_on_screen': round(frames / 16, 1), 'outcome': outcome,
            'elapsed_s': round(time.monotonic() - started),
            'lowest_available_gib': round(min(seen), 1) if seen else None, 'finished_at': time.strftime('%F %T')}


def main():
    drawing, out, lengths = Path(sys.argv[1]), Path(sys.argv[2]), [int(n) for n in sys.argv[3:]]
    out.mkdir(parents=True, exist_ok=True)
    media_server.JOB_DEADLINE_S = 3 * 3600
    instruction = class_instruction(ACTION)
    aside = media_spark.RESIDENT / f'waiting-{os.getpid()}-trial'   # the keepers do not reload between lengths
    media_spark.RESIDENT.mkdir(parents=True, exist_ok=True)
    aside.write_text(str(os.getpid()))
    try:
        for frames in lengths:
            result = one_clip(drawing, instruction, frames, out)
            print(json.dumps(result), flush=True)
            with (out / 'results.jsonl').open('a') as log:
                log.write(json.dumps(result) + '\n')
    finally:
        aside.unlink(missing_ok=True)
        media_spark.resume_reader()
        media_spark.resume_resident()
        media_spark.resume_front()


if __name__ == '__main__':
    main()
