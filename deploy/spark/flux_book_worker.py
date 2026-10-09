"""FLUX.2 Klein 4B redraws a storybook's pages in a picture-book style, kept loaded while a book is being made.

A job is either page 1 in each of the styles, for the teacher to choose from, or the rest of the book in the style
she chose. Loading takes ~22 s and a page ~4.5 s (measured on the Spark:
docs/measured/storybook-styles.md), and every job used to load it again: of the 81 s the
rest of a five-page book took, ~45 s were two loads, one for the pages and one for a page drawn again after its
check (operator: keep it warm). So the first job of a book starts this process, it stays loaded, and it leaves
once no job has come for IDLE_S seconds, giving its ~22 GiB back; a clip or a 3D job that needs the room sends it
away first (media_spark.room_for). Loaded the way the GB10 needs, as the retired still pose was: nothing offloaded,
no weight file memory-mapped (fast_load.py).

It listens on the Unix socket /resident/flux-book.sock, made once the model is loaded, so its presence means ready.
One connection is one job: the client (flux_client.py) sends the job folder's name and a newline; the folder under
/jobs holds request.json ({"pictures": [{"image": data URI, "instruction": str, "seed": int}]}), this writes
output.json ({"pictures": [base64 JPEG, ...]}) beside it in the same order, and answers `ok` or `error <kind>`.
It prints no instruction and no picture: media_server.py keeps the log on the node. The drawing imports stay
inside the functions so the serving can be tested without a chip.
"""
import base64
import io
import json
import os
import socketserver
import sys
import time
from pathlib import Path

# The long side a page is drawn at. At the drawing's full 1536 the child's picture held the style back and
# four of six styles came out looking like the original; at 1024, with the must-keep list in the
# instruction, every style showed and every character stayed.
SIDE = 1024
SOCKET = Path('/resident/flux-book.sock')
JOBS = Path('/jobs')
IDLE_S = 180.0   # "a few minutes" after a book's last job (operator)


def load():
    import torch
    from diffusers import Flux2KleinPipeline
    from transformers import Qwen3ForCausalLM
    from fast_load import text_encoder
    return Flux2KleinPipeline.from_pretrained(
        '/models/flux', torch_dtype=torch.bfloat16, local_files_only=True, disable_mmap=True,
        text_encoder=text_encoder(Qwen3ForCausalLM, '/models/flux/text_encoder', torch.bfloat16),
    ).to('cuda')


def draw(pipe, picture):
    import torch
    from PIL import Image
    source = Image.open(io.BytesIO(base64.b64decode(picture['image'].partition(',')[2]))).convert('RGB')
    source.thumbnail((SIDE, SIDE))
    width, height = (max(64, n // 16 * 16) for n in source.size)
    image = pipe(prompt=picture['instruction'], image=source, width=width, height=height,
                 num_inference_steps=4, guidance_scale=1.0,
                 generator=torch.Generator('cpu').manual_seed(int(picture.get('seed', 42)))).images[0]
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=90)
    return base64.b64encode(out.getvalue()).decode()


def draw_job(pipe, job):
    pictures = json.loads((job / 'request.json').read_text())['pictures']
    drawn = []
    for n, picture in enumerate(pictures, 1):
        drawn.append(draw(pipe, picture))
        print(f'page picture {n} of {len(pictures)} drawn', flush=True)
    (job / 'output.json').write_text(json.dumps({'pictures': drawn}))


def serve(work, socket_path=SOCKET, jobs=JOBS, idle_s=IDLE_S, after_failure=lambda: os._exit(1), name='FLUX.2 Klein 4B'):
    """Answer one job per connection with work(job_folder), until none has come for idle_s seconds.

    Idle is counted from the last job, not the last connection: media_spark looks whether this answers before
    other media jobs too, and a look is not a reason to keep ~22 GiB. A job that fails ends the process once the
    answer is sent, as the kept-loaded 3D model does: an error on the chip can leave the model unusable while
    the socket still accepts, and the next job starts a fresh one.
    """
    root, last = Path(jobs).resolve(), [time.monotonic()]

    class Job(socketserver.StreamRequestHandler):
        def handle(self):
            name = self.rfile.readline(256).decode('utf-8', 'replace').strip()
            if not name:   # media_spark.flux_warm seeing whether we answer
                return
            job = (root / name).resolve()
            if job.parent != root or not (job / 'request.json').is_file():
                self.wfile.write(b'error bad-job\n')
                return
            try:
                work(job)
            except Exception as error:
                self.wfile.write(f'error {type(error).__name__}\n'.encode())
                self.wfile.flush()
                after_failure()
                return
            finally:
                last[0] = time.monotonic()
            self.wfile.write(b'ok\n')

    socket_path = Path(socket_path)
    socket_path.unlink(missing_ok=True)
    with socketserver.UnixStreamServer(str(socket_path), Job) as server:
        os.chmod(socket_path, 0o600)
        print(name, 'loaded; answering on', socket_path, flush=True)
        while (left := idle_s - (time.monotonic() - last[0])) > 0:
            server.timeout = left
            server.handle_request()
    socket_path.unlink(missing_ok=True)
    print(f'no job for {idle_s:.0f} s; letting {name} go', flush=True)


if __name__ == '__main__':
    sys.path.insert(0, '/spark')
    idle = float(sys.argv[sys.argv.index('--idle') + 1]) if '--idle' in sys.argv else IDLE_S
    pipe = load()
    serve(lambda job: draw_job(pipe, job), idle_s=idle)
