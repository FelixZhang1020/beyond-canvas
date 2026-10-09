"""VoxCPM2 on the 4090; no weights are loaded by the classroom Mac.

The worker at the other end of ``base_url`` runs one job at a time
(``self.server.busy`` in media_server.py) and answers 503 with
``{"error": "worker queue full"}`` to anyone who asks while it is occupied —
expected whenever a multi-line reply queues its next sentence before the
worker has released the previous one, and ordinary because ``_course_speech``
builds a fresh, disposable SpeechSession per request (serve.py), so an
in-flight line has no way to be told a later click replaced it: the earlier
line keeps the worker busy for its own full cold-load, measured at 15-16 s
(docs/measured/), until it finishes on its own. Waiting a few seconds and
giving up is waiting for less than one such line takes; the retry budget
below is sized to outlast one, not to paper over a genuinely stuck worker.
Any other status is a real failure and is not retried.
"""
import base64
import io
import json
import time
import wave
from studio.voice.audio_in import UnreadableAudio, as_mp3
from studio.core.errors import ModelError
from studio.providers.gpu_job import stream_job
import httpx
from studio.providers.localvideo import LocalVideoClient
from studio.providers.stepfun_voice import VoiceServiceError

BUSY_RETRIES = 11
BUSY_POLL_INTERVAL_S = 2.0


def _reason(response):
    """The worker's own explanation, when it sent one, else the bare status."""
    try:
        body = json.loads(response.read())
        if isinstance(body, dict) and isinstance(body.get('error'), str):
            return f"{response.status_code} {body['error']}"
    except (httpx.HTTPError, ValueError):
        pass
    return f'status {response.status_code}'


def _fetch(client, base_url, body, cancelled, timeout=180):
    """The worker's raw WAV bytes, retrying past a busy worker queue; None if cancelled."""
    reason = None
    for attempt in range(BUSY_RETRIES):
        if attempt:
            print(f'remotevoice: worker queue full, retry {attempt}/{BUSY_RETRIES - 1} '
                  f'in {BUSY_POLL_INTERVAL_S:.1f}s ({reason})', flush=True)
            time.sleep(BUSY_POLL_INTERVAL_S)
        if cancelled(): return None
        content = bytearray()
        with stream_job(client, base_url, '/v1/audio/speech', body=body, timeout=timeout,
                        cancelled=cancelled) as response:
            if response.status_code == 503 and attempt < BUSY_RETRIES - 1:
                reason = _reason(response)
                continue
            if response.status_code != 200:
                reason = _reason(response)
                print(f'remotevoice: giving up after {attempt + 1} attempt(s) ({reason})', flush=True)
                raise VoiceServiceError(f'Local speech is unavailable ({reason})')
            for chunk in response.iter_bytes(65536):
                if cancelled(): return None
                if len(content)+len(chunk)>8_000_000: raise VoiceServiceError('Speech exceeds limit')
                content.extend(chunk)
        return content
    print(f'remotevoice: giving up after {BUSY_RETRIES} attempt(s) ({reason})', flush=True)
    raise VoiceServiceError(f'Local speech is unavailable ({reason})')


class RemoteChildVoice:
    """VoxCPM2 on the Spark reading a storybook page in a child's copied voice (studio/voice/child_voice.py).

    The media service there (media_spark.py --kind voice, 7280) keeps the model loaded while a book is read
    (voice_book_worker.py); the first page waits for its load. Sent: the page and the kept recording, which
    goes no further than the Spark. Back: the page as MP3, what the class's link carries (studio/voice/audio_in.py).
    """
    model = 'VoxCPM2'

    def __init__(self, options=None, client=None):
        endpoint = LocalVideoClient('VoxCPM2', options, client)
        self.base_url, self._client = endpoint.base_url, endpoint._client
        self.timeout = float((options or {}).get('timeout_s', 300))

    def read(self, reference, text, cancelled=lambda: False, said=''):
        """The text in the voice of `reference` (a WAV) and the words `said` in it, as MP3; None if cancelled,
        VoiceServiceError if not made. Without its words the copy drifts sentence to sentence (child_voice.py)."""
        body = {'model': 'VoxCPM2', 'voice': 'child', 'input': text.strip(),
                'reference': base64.b64encode(reference).decode('ascii')}
        if said:
            body['reference_text'] = said
        try:
            content = _fetch(self._client, self.base_url, body, cancelled, self.timeout)
        except (httpx.HTTPError, ModelError):
            raise VoiceServiceError('The Spark could not read this page in the child\'s voice') from None
        if content is None:
            return None
        if content[:4] != b'RIFF' or content[8:12] != b'WAVE':
            raise VoiceServiceError('The Spark sent back something other than a recording')
        try:
            return as_mp3(bytes(content))
        except UnreadableAudio:
            raise VoiceServiceError('The page could not be made into MP3') from None


class RemoteClassroomVoice:
    local = False
    model = 'VoxCPM2'
    sample_rate = 24000
    voice = 'gentle-female'
    voices = {'gentle-female':'温柔女声','gentle-male':'温和男声','soft-child':'童声 A'}

    def __init__(self, options=None, client=None):
        endpoint = LocalVideoClient('VoxCPM2', options, client)
        self.base_url, self._client = endpoint.base_url, endpoint._client

    def validate_voice(self, voice):
        if not isinstance(voice, str) or voice not in self.voices: raise ValueError('Unknown voice')
        return voice

    def _fetch(self, text, voice_id, cancelled):
        """The worker's raw WAV bytes, retrying past a busy worker queue."""
        return _fetch(self._client, self.base_url, {'input': text.strip(), 'voice': voice_id}, cancelled)

    def stream(self, text, voice_id=voice, cancelled=lambda:False):
        self.validate_voice(voice_id)
        if not isinstance(text,str) or not 1 <= len(text.strip()) <= 400:
            raise ValueError('Speech requires 1–400 characters')
        if cancelled(): return
        try:
            content = self._fetch(text, voice_id, cancelled)
            if content is None: return
            with wave.open(io.BytesIO(content),'rb') as audio:
                if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate()) != (1,2,24000):
                    raise VoiceServiceError('Unexpected speech format')
                frames = audio.getnframes()
                if audio.getcomptype() != 'NONE' or not 0 < frames <= self.sample_rate * 120:
                    raise VoiceServiceError('Unexpected speech duration')
                pcm = audio.readframes(frames)
                if len(pcm) != frames * 2:
                    raise VoiceServiceError('Truncated speech response')
                for offset in range(0, len(pcm), 8192):
                    if cancelled(): return
                    yield pcm[offset:offset + 8192]
        except (httpx.HTTPError,wave.Error,EOFError):
            raise VoiceServiceError('4090 speech is unavailable') from None
