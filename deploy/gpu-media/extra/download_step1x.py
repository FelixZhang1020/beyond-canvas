"""Download only the original Step1X model and its required encoder, pinned."""
from pathlib import Path
from huggingface_hub import snapshot_download
root = Path.home() / 'beyond-canvas-deploy/media-extra/step1x-model'
for repo, revision, target, patterns in [
 ('stepfun-ai/Step1X-Edit', '752c0bc28a43f56249f588432a5964f1878c01ff', root,
  ['config.json', 'vae.safetensors', 'step1x-edit-i1258.safetensors', 'LICENSE']),
 ('Qwen/Qwen2.5-VL-7B-Instruct', 'cc594898137f460bfe9f0759e9844b3ce807cfb5', root / 'Qwen2.5-VL-7B-Instruct',
  ['*.json', '*.safetensors', '*.txt', '*.model']),
]:
    snapshot_download(repo, revision=revision, local_dir=target, allow_patterns=patterns, max_workers=3)
    (target / '.pinned-revision').write_text(revision + '\n')
    print(repo, revision, 'complete', flush=True)
