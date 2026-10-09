"""Precompute one prompt cache per voice, so no lesson pays to encode them.

Run once on the 4090 after the voice weights or the reference wavs change.
voice_worker.py names each cache by a fingerprint of both, so an out-of-date
file is ignored rather than used; this script simply builds the current ones.
Writes into /voices, which the worker itself mounts read-only.
"""
import sys
import torch
from voxcpm import VoxCPM
sys.path.insert(0, '/runner')
from voice_worker import prompt_cache_key  # noqa: E402  (same fingerprint, one definition)

VOICES = ('gentle-female', 'gentle-male', 'soft-child')

model = VoxCPM.from_pretrained('/models/voice', load_denoiser=False, local_files_only=True,
                               optimize=False, device='cuda').tts_model
for voice in VOICES:
    reference = f'/voices/{voice}.wav'
    target = f'/voices/{voice}.{prompt_cache_key(reference)}.cache.pt'
    cache = model.build_prompt_cache(reference_wav_path=reference)
    # Saved verbatim: the worker must get back what building would have given it,
    # including which device each tensor sits on, and any key a later VoxCPM adds.
    torch.save(cache, target)
    print('wrote', target, flush=True)
