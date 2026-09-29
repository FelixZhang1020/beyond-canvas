"""Hearing on the Spark: Whisper on the node's own chip, answering like a whisper.cpp server.

Operator: look into transcribing on our own hardware again. Every class since Local First was
archived has sent a child's recorded voice to StepFun; the node has an idle chip and Whisper's
weights are open, so the recording need not leave the hardware the operator rents. Nothing about
the studio changes: studio/voice/transcribe.py's WhisperCppClient has always posted the recording to
`/inference` and read `{"text": ...}` back, so this serves that same shape and a profile only has
to name this address.

The recording is never written to disk here either: it is decoded in memory, transcribed, and
dropped. Run in the container built by build-hearing.sh, which has ffmpeg for the page's webm.

    python3 hearing_worker.py [--port 7290] [--model /models/whisper]
"""
import argparse
import json
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy
import torch
from transformers import pipeline

SIXTEEN_K = 16000
PART = re.compile(rb'name="([^"]+)"(?:; filename="[^"]*")?\r\n(?:[^\r\n]+\r\n)*\r\n', re.S)


def fields(body: bytes, boundary: bytes) -> dict[str, bytes]:
    """The multipart form as {name: raw bytes}, enough for one file and a few strings."""
    out = {}
    for chunk in body.split(b'--' + boundary):
        match = PART.search(chunk)
        if match:
            out[match.group(1).decode()] = chunk[match.end():].rstrip(b'\r\n-')
    return out


def audio_of(raw: bytes) -> numpy.ndarray:
    """Whatever the page recorded, as the mono 16 kHz floats the model wants."""
    done = subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', 'pipe:0',
         '-f', 'f32le', '-ac', '1', '-ar', str(SIXTEEN_K), 'pipe:1'],
        input=raw, capture_output=True, check=True)
    return numpy.frombuffer(done.stdout, dtype=numpy.float32)


class Hearing(BaseHTTPRequestHandler):
    def do_GET(self) -> None:                                    # noqa: N802 - http.server's own name
        if self.path.rstrip('/') in ('/v1/models', '/health'):
            self._json(200, {'object': 'list', 'data': [{'id': self.server.model_name}]})
        else:
            self._json(404, {'error': 'only /inference and /v1/models'})

    def do_POST(self) -> None:                                   # noqa: N802
        if self.path.rstrip('/') != '/inference':
            self._json(404, {'error': 'only /inference'})
            return
        kind = self.headers.get('Content-Type', '')
        if 'boundary=' not in kind:
            self._json(400, {'error': 'send the recording as a multipart form'})
            return
        body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        form = fields(body, kind.split('boundary=')[1].strip('"').encode())
        if not form.get('file'):
            self._json(400, {'error': 'no file in the form'})
            return
        language = (form.get('language') or b'zh').decode().strip() or 'zh'
        prompt = (form.get('prompt') or b'').decode().strip()
        try:
            heard = self.server.hear(audio_of(form['file']), language, prompt)
        except subprocess.CalledProcessError as error:
            self._json(400, {'error': f'the recording could not be read: {error.stderr[-200:]}'})
        except Exception as error:                               # noqa: BLE001 - the studio reads the text
            self._json(500, {'error': f'{type(error).__name__}: {error}'})
        else:
            self._json(200, {'text': heard})

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:           # one line per request, no recording in it
        sys.stderr.write(f'{self.log_date_time_string()} {format % args}\n')


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=7290)
    parser.add_argument('--model', default='/models/whisper')
    arguments = parser.parse_args(argv)

    listener = pipeline('automatic-speech-recognition', model=arguments.model,
                        torch_dtype=torch.float16, device='cuda')
    tokenizer = listener.tokenizer

    def hear(audio: numpy.ndarray, language: str, prompt: str) -> str:
        """One recording to one sentence. A prompt in simplified Chinese keeps the answer simplified."""
        generate = {'language': language, 'task': 'transcribe'}
        if prompt:
            generate['prompt_ids'] = tokenizer.get_prompt_ids(prompt, return_tensors='pt').to('cuda')
            generate['prompt_condition_type'] = 'first-segment'
        answer = listener({'raw': audio, 'sampling_rate': SIXTEEN_K},
                          generate_kwargs=generate, return_timestamps=False)
        return str(answer.get('text', '')).strip()

    server = ThreadingHTTPServer(('127.0.0.1', arguments.port), Hearing)
    server.hear, server.model_name = hear, arguments.model.rstrip('/').rsplit('/', 1)[-1]
    print(f'hearing on {arguments.port} with {server.model_name}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
