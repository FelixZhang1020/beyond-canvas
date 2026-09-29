"""Verify downloaded weight files against their HF SHA-256 metadata."""
import argparse
import hashlib
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('root',type=Path)
a=p.parse_args()
rows=[]
for meta in sorted((a.root/'.cache/huggingface/download').rglob('*.metadata')):
    lines=meta.read_text().splitlines()
    if len(lines)<2:raise RuntimeError('invalid metadata')
    expected=lines[1].strip('"')
    if len(expected)!=64:continue
    relative=meta.relative_to(a.root/'.cache/huggingface/download').as_posix().removesuffix('.metadata')
    target=a.root/relative
    h=hashlib.sha256()
    with target.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    if h.hexdigest()!=expected:raise RuntimeError('weight checksum mismatch: '+relative)
    rows.append(h.hexdigest()+'  '+relative)
if not rows:raise RuntimeError('no hashed weights found')
(a.root/'verified-sha256.txt').write_text('\n'.join(rows)+'\n')
print('verified',len(rows),'weight files',flush=True)
