"""VoxCPM2 reads a storybook page in a child's own voice, kept loaded while a book is read (operator).

A job is one sentence of a page (studio/voice/child_voice.py sends them one at a time, so the first is heard after a
few seconds), and the first answer the child said out loud about that page's drawing: at most ten seconds of it,
and the words heard in it (reference_text) when none were cut off. The copy lives only while the page is read: the
features made from the recording are zeroed after every page, as the voice lab did, and nothing is written but
the page's WAV.

Loaded once, like the storybook's FLUX (flux_book_worker.py, whose serving this uses): the first page of a book
starts this process, later pages are handed to it, and it leaves once no page has come for IDLE_S, giving its
memory back; a clip or a 3D job that needs the room sends it away first (media_spark.room_for).

request.json: {"input": sentence, "reference": base64 WAV, "reference_text": optional};
output.wav: 24 kHz mono 16-bit, as the 4090's voice worker wrote (deploy/gpu-media/extra/voice_worker.py).
It prints no text and no recording.
"""
import base64
import io
import json
import sys
from pathlib import Path

SOCKET = Path('/resident/voice-book.sock')
IDLE_S = 600.0   # a teacher reads a book page by page, and comes back to it; ten minutes between pages


def load():
    """VoxCPM2 as measured best on the Spark: its compiled mode loaded in 54 s and read slower."""
    import torch
    from voxcpm import VoxCPM
    torch.set_num_threads(8)
    model = VoxCPM.from_pretrained('/models/voice', load_denoiser=False, local_files_only=True,
                                   optimize=False, device='cuda').tts_model
    warm_up(model)
    return model


def warm_up(model):
    """Copy a voice once before the first page does: the first copy after a load took 6.4 s, later ones 0.04 s."""
    import numpy as np
    import soundfile as sf
    tone = (0.2 * np.sin(np.arange(32000) * 2 * np.pi * 220 / 16000)).astype(np.float32)
    held = io.BytesIO()
    sf.write(held, tone, 16000, format='WAV', subtype='PCM_16')
    held.seek(0)
    cache = model.build_prompt_cache(reference_wav_path=held)
    hello = '\u4f60\u597d\u3002'
    for _ in model.generate_with_prompt_cache_streaming(target_text=hello, prompt_cache=cache, max_len=50):
        pass
    cache.clear()


END, PAUSE = '\u3002\uff01\uff1f\uff1b!?;', '\uff0c\u3001,'   # full stops, then commas


def sentences(text, most=60):
    """The page a sentence at a time: VoxCPM2 reads a sentence well and a paragraph less well."""
    pieces, piece = [], ''
    for character in text.strip():
        piece += character
        if character in END or (len(piece) >= most and character in PAUSE):
            pieces.append(piece.strip())
            piece = ''
    return [p for p in pieces + [piece.strip()] if p]


def speak(model, job):
    import numpy as np
    import soundfile as sf
    import torch
    from scipy.signal import resample_poly
    asked = json.loads((job / 'request.json').read_text())
    recording = base64.b64decode(asked['reference'])
    # With the words heard in it, VoxCPM2 follows the voice: a 148 Hz voice came out at 148. From the recording
    # alone its sentences wandered from 119 to 207 Hz (docs/measured/child-voice.md).
    if asked.get('reference_text'):
        cache = model.build_prompt_cache(prompt_text=asked['reference_text'], prompt_wav_path=io.BytesIO(recording),
                                         reference_wav_path=io.BytesIO(recording))
    else:
        cache = model.build_prompt_cache(reference_wav_path=io.BytesIO(recording))
    try:
        parts, frames = [], 0
        for sentence in sentences(asked['input']):
            torch.manual_seed(42)   # VoxCPM 2.0.3 takes no seed of its own; the same page reads the same way
            # Whole, not streamed: VoxCPM reads a sentence again when it comes out far too long or short for its
            # words only outside streaming, and a job is answered whole anyway.
            wav, _, _ = model.generate_with_prompt_cache(
                target_text=sentence, prompt_cache=cache, cfg_value=2.0, inference_timesteps=10,
                max_len=750, retry_badcase=True)
            part = wav.detach().cpu().float().numpy().reshape(-1)
            frames += len(part)
            if frames > model.sample_rate * 120 or not np.isfinite(part).all():
                raise ValueError('invalid or overlong audio')
            parts += [part, np.zeros(int(model.sample_rate * .25), dtype=np.float32)]   # a breath between sentences
        audio = np.concatenate(parts) if parts else np.zeros(0)
        if not len(audio) or np.max(np.abs(audio)) < .001:
            raise ValueError('silent audio')
        sf.write(str(job / 'output.wav'), resample_poly(audio, 24000, model.sample_rate), 24000, subtype='PCM_16')
    finally:
        with torch.inference_mode():   # the child's voice features, gone before the next page is asked
            for value in cache.values():
                if isinstance(value, torch.Tensor):
                    value.zero_()
            for lm in (model.base_lm, model.residual_lm):
                lm.kv_cache.kv_cache.zero_()
                lm.kv_cache.current_length = 0
        cache.clear()


if __name__ == '__main__':
    sys.path.insert(0, '/spark')
    from flux_book_worker import serve
    idle = float(sys.argv[sys.argv.index('--idle') + 1]) if '--idle' in sys.argv else IDLE_S
    loaded = load()
    serve(lambda job: speak(loaded, job), socket_path=SOCKET, idle_s=idle, name='VoxCPM2')
