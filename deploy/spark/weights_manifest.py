"""Every media weight the Spark runs: where it comes from, where it goes, how it is checked.

This is the one list. The node cannot reach Hugging Face, so the weights come
from ModelScope; but the revisions this project pins are Hugging Face's (see
deploy/trellis2/versions.env), so `make` reads the official checksums at those
revisions on a machine that can reach huggingface.co and writes them beside
this file as weights.sha256, and `check` holds every downloaded file on the node
to them. A ModelScope copy is used only if it is byte-identical.

MoGe has no copy under its own name on ModelScope. `rookie6667/moge-2-vitl`
carried a model.pt with the official SHA-256 when it was checked; `check` is what
makes that safe to rely on, since model.pt is a pickle and runs code on load.

    python3 deploy/spark/weights_manifest.py make                 # Mac → weights.sha256
    ~/tools/bin/python deploy/spark/weights_manifest.py fetch      # node, capped, resumable
    python3 deploy/spark/weights_manifest.py check                # node
"""
import hashlib
import json
import os
import sys
import urllib.request
from fnmatch import fnmatch
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'weights.sha256'
HUB = 'trellis/models/huggingface/hub'
PIXAL_CKPTS = ('ss_dec_conv3d_16l8_fp16', 'ss_flow_img_dit_1_3B_64_bf16', 'shape_dec_next_dc_f16c32_fp16',
               'slat_flow_img2shape_dit_1_3B_512_bf16', 'slat_flow_img2shape_dit_1_3B_1024_bf16',
               'tex_dec_next_dc_f16c32_fp16', 'slat_flow_imgshape2tex_dit_1_3B_1024_bf16')


def hub(repo, revision):
    return f'{HUB}/models--{repo.replace("/", "--")}/snapshots/{revision}'


# (Hugging Face repo, pinned revision, ModelScope repo, destination under ~, files)
ENTRIES = [
    ('facebook/dinov3-vitl16-pretrain-lvd1689m', 'ea8dc2863c51be0a264bab82070e3e8836b02d51', None,
     ['config.json', 'model.safetensors', 'preprocessor_config.json']),
    ('briaai/RMBG-2.0', '5df4c9c76d8170882c34f6986e848ee07fd0ba43', None,
     ['BiRefNet_config.py', 'birefnet.py', 'config.json', 'model.safetensors', 'preprocessor_config.json']),
    ('microsoft/TRELLIS-image-large', '25e0d31ffbebe4b5a97464dd851910efc3002d96', None,
     ['ckpts/ss_dec_conv3d_16l8_fp16.*']),
    ('Ruicheng/moge-2-vitl', '39c4d5e957afe587e04eec59dc2bcc3be5ecd968', 'rookie6667/moge-2-vitl', ['model.pt']),
    ('microsoft/TRELLIS.2-4B', 'af44b45f2e35a493886929c6d786e563ec68364d', None, ['pipeline.json', 'ckpts/*']),
    ('TencentARC/Pixal3D', 'b0cb2e1b794cab9aa0ac38a95d794a4d9337437f', None,
     ['pipeline.json'] + [f'ckpts/{name}.*' for name in PIXAL_CKPTS]),
    ('black-forest-labs/FLUX.2-klein-4B', 'e7b7dc27f91deacad38e78976d1f2b499d76a294', None, ['*']),
    ('Wan-AI/Wan2.2-I2V-A14B-Diffusers', '596658fd9ca6b7b71d5057529bbf319ecbc61d74', None, ['*']),
]
DESTINATIONS = {'TencentARC/Pixal3D': 'pixal3d/models/Pixal3D',
                'black-forest-labs/FLUX.2-klein-4B': 'models/flux2-klein-4b',
                'Wan-AI/Wan2.2-I2V-A14B-Diffusers': 'models/wan2.2-i2v-a14b-diffusers'}


def destination(repo, revision):
    return DESTINATIONS.get(repo) or hub(repo, revision)


def make():
    """Official checksums at the pinned revisions, from huggingface.co."""
    lines = [f'# made by `python3 deploy/spark/weights_manifest.py make` from huggingface.co']
    for repo, revision, _, patterns in ENTRIES:
        url = f'https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=true'
        with urllib.request.urlopen(url, timeout=60) as response:
            tree = json.load(response)
        files = [f for f in tree if f['type'] == 'file' and any(fnmatch(f['path'], p) for p in patterns)]
        if not files:
            raise SystemExit(f'{repo}@{revision}: nothing matches {patterns}')
        for f in files:
            algorithm, value = ('sha256', f['lfs']['oid']) if f.get('lfs') else ('gitsha1', f['oid'])
            if '*' in value:
                # Gated repos mask their large files' checksums to anyone signed out
                # (dinov3 and RMBG-2.0). Their small files, the RMBG code
                # included, still carry real ones; a .safetensors cannot run code, so
                # for those two the size is checked and nothing stronger is claimed.
                algorithm, value = 'size', '-'
            lines.append(f'{algorithm} {value} {f["size"]} {destination(repo, revision)}/{f["path"]}')
    MANIFEST.write_text('\n'.join(lines) + '\n')
    print(f'{len(lines) - 1} files written to {MANIFEST}')


def fetch():
    """Download every entry from ModelScope at the capped rate, then point refs/main at it."""
    sys.path.insert(0, str(HERE))
    from fetch_weights import run
    rate = float(os.environ.get('RATE', '6'))
    for repo, revision, mirror, patterns in ENTRIES:
        target = Path.home() / destination(repo, revision)
        run(mirror or repo, target, patterns, rate)
        if target.parent.name == 'snapshots':
            refs = target.parent.parent / 'refs'
            refs.mkdir(exist_ok=True)
            (refs / 'main').write_text(revision)


def digest(path, algorithm, size):
    h = hashlib.sha256() if algorithm == 'sha256' else hashlib.sha1(f'blob {size}\0'.encode())
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(16 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check():
    """Every file in weights.sha256 against the node's copy; exit 1 on any difference."""
    problems = 0
    for line in MANIFEST.read_text().splitlines():
        if line.startswith('#'):
            continue
        algorithm, expected, size, relative = line.split(' ', 3)
        path = Path.home() / relative
        if not path.is_file():
            print(f'MISSING  {relative}')
            problems += 1
        elif algorithm == 'size':
            if path.stat().st_size != int(size):
                print(f'MISMATCH {relative} (size)')
                problems += 1
        elif digest(path, algorithm, int(size)) != expected:
            print(f'MISMATCH {relative}')
            problems += 1
    print('all files match the pinned checksums' if not problems else f'{problems} problem(s)')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    {'make': make, 'fetch': fetch, 'check': check}[sys.argv[1]]()
