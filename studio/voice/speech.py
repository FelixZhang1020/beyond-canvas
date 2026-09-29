"""Classroom speech, a sentence at a time: the studio's own voice, or the child's copied from its kept answer."""
import base64
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

from studio.providers.stepfun_voice import MP3_LIMIT, VoiceServiceError


@dataclass
class SpeechSession:
    cache: OrderedDict = field(default_factory=OrderedDict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    stopped: threading.Event = field(default_factory=threading.Event)
    closed: bool = False

    def stop(self, *, close=False):
        with self.lock:
            self.stopped.set()
            if close:
                self.closed = True
                self.cache.clear()

    def stream(self, voice, text, voice_id):
        if voice is None:
            raise VoiceServiceError("Classroom speech is unavailable.")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 400:
            raise ValueError("Speech requires 1–400 characters.")
        voice_id = voice.validate_voice(voice_id or voice.voice)
        text = text.strip()
        with self.lock:
            if self.closed:
                raise KeyError("Class has ended.")
            self.stopped.set()
            cancelled = self.stopped = threading.Event()
            key = (id(voice), getattr(voice, "model", ""), getattr(voice, "base_url", ""), text, voice_id)
            cached = self.cache.get(key)
        return self._events(voice, text, voice_id, key, cached, cancelled)

    def _events(self, voice, text, voice_id, key, cached, cancelled):
        chunks = []
        results = None
        # A voice that says it is compressed yields whole MP3 sentences, which the page decodes one at
        # a time; any other yields raw 16-bit sound (studio/providers/stepfun_voice.py says why).
        kind = "mp3" if getattr(voice, "compressed", False) else "pcm"
        limit = MP3_LIMIT if kind == "mp3" else voice.sample_rate * 2 * 120
        try:
            yield {"type": "format", "sample_rate": voice.sample_rate, "cached": cached is not None}
            results = iter(cached) if cached is not None else voice.stream(text, voice_id, cancelled.is_set)
            size = 0
            for piece in results:
                if cancelled.is_set():
                    return
                size += len(piece)
                if size > limit:
                    raise VoiceServiceError("Speech exceeded the playback limit.")
                chunks.append(piece)
                yield {"type": kind, "data": base64.b64encode(piece).decode("ascii")}
            with self.lock:
                if cancelled.is_set() or self.closed:
                    return
                if not chunks:
                    raise VoiceServiceError("Speech returned no audio.")
                self.cache[key] = tuple(chunks)
                self.cache.move_to_end(key)
                while (len(self.cache) > 12 or
                       sum(sum(map(len, parts)) for parts in self.cache.values()) > 16 * 1024 * 1024):
                    self.cache.popitem(last=False)
            yield {"type": "done"}
        finally:
            if results is not None and hasattr(results, "close"):
                results.close()


def load_local_voice(model_path, source_path, device):
    import os
    import sys
    from pathlib import Path
    from studio.providers.voxcpm_voice import VoxCPMRuntime, VoxCPMDialogueVoice

    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")
    sys.path.insert(0, str(Path(source_path).resolve()))
    runtime = VoxCPMRuntime(model_path, Path(__file__).parents[1] / "voice_lab" / "voices", device)
    return VoxCPMDialogueVoice(runtime)
