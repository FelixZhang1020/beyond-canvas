"""VoxCPM2 CUDA worker using only the three public synthetic references."""
import hashlib
import json
import os
import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly
from voxcpm import VoxCPM


def prompt_cache_key(reference):
    """Name a cache by everything it derives from, so a stale one cannot be read.

    The reference wav decides the timbre and the weights decide the encoding, so
    a cache that outlived either would synthesise the wrong voice — a fault no
    error surfaces and only an ear would catch. Both are cheap to fingerprint:
    the references are a few hundred KB, and the revision is a pinned string.
    """
    revision = ''
    try:
        revision = open('/models/voice/.pinned-revision').read().strip()
    except OSError:
        pass
    with open(reference, 'rb') as handle:
        return hashlib.sha256(handle.read() + revision.encode()).hexdigest()[:16]


def main():
    p = json.load(open('/job/request.json'))
    torch.set_num_threads(8)
    model = VoxCPM.from_pretrained('/models/voice', load_denoiser=False, local_files_only=True,
                                   optimize=False, device='cuda').tts_model
    # Encoding the reference wav costs 6.8 s and produces the same tensor every time
    # for a given voice and revision (measured). Read it back instead when
    # one has been built; falling back to building keeps the worker correct on a box
    # where the caches were never generated.
    reference = '/voices/' + p['voice'] + '.wav'
    cached = f'/voices/{p["voice"]}.{prompt_cache_key(reference)}.cache.pt'
    if os.path.exists(cached):
        # Load it exactly as it was built. build_prompt_cache returns the feature
        # on the CPU and the model moves it itself; forcing it onto the GPU here
        # looks like the obvious thing and breaks generation, surfacing far away
        # as a device mismatch inside _make_ref_prefix rather than at this line.
        cache = torch.load(cached, weights_only=True)
    else:
        cache = model.build_prompt_cache(reference_wav_path=reference)
    parts = []
    frames = 0
    for wav, _, _ in model.generate_with_prompt_cache_streaming(
            target_text=p['input'], prompt_cache=cache, cfg_value=2.0,
            inference_timesteps=10, max_len=750, retry_badcase=False, seed=42):
        part = wav.detach().cpu().float().numpy().reshape(-1)
        frames += len(part)
        if frames > 48000 * 120 or not np.isfinite(part).all():
            raise ValueError('invalid or overlong audio')
        parts.append(part)
    audio = np.concatenate(parts)
    if not len(audio) or np.max(np.abs(audio)) < .001:
        raise ValueError('silent audio')
    sf.write('/job/output.wav', resample_poly(audio, 1, 2), 24000, subtype='PCM_16')


if __name__ == '__main__': main()
