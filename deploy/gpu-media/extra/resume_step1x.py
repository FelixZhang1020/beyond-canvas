"""Finish a public pinned checkpoint via validated byte ranges and SHA-256.

Only the suffix is downloaded; the existing HF prefix remains untouched until
an independently assembled file has passed the server-provided content hash.
"""
import concurrent.futures
import hashlib
import os
from pathlib import Path
import signal
import time
import httpx
from huggingface_hub import get_hf_file_metadata, hf_hub_url

root=Path.home()/'beyond-canvas-deploy/media-extra/step1x-model'
repo='stepfun-ai/Step1X-Edit'
revision='752c0bc28a43f56249f588432a5964f1878c01ff'
filename='step1x-edit-i1258.safetensors'
url=hf_hub_url(repo,filename,revision=revision,endpoint='https://hf-mirror.com')
meta=get_hf_file_metadata(url)
incomplete=max((root/'.cache/huggingface/download').glob('*.incomplete'),key=lambda p:p.stat().st_size)
prefix=incomplete.stat().st_size
parts=root/'.range-suffix';parts.mkdir(exist_ok=True)
width=(meta.size-prefix+5)//6

def fetch(index):
    start=prefix+index*width
    end=min(meta.size-1,start+width-1)
    path=parts/str(index)
    if start>end:return path,0
    expected=end-start+1
    for attempt in range(3):
        offset=path.stat().st_size if path.exists() else 0
        if offset==expected:return path,expected
        if offset>expected:raise RuntimeError('range size mismatch')
        try:
            with httpx.stream('GET',meta.location,headers={'Range':f'bytes={start+offset}-{end}'},follow_redirects=True,timeout=60) as response:
                if response.status_code!=206 or response.headers.get('Content-Range')!=f'bytes {start+offset}-{end}/{meta.size}':
                    raise RuntimeError('range response rejected')
                with path.open('ab') as target:
                    for chunk in response.iter_bytes(4*1024*1024):target.write(chunk)
            if path.stat().st_size==expected:return path,expected
        except (httpx.HTTPError, OSError):
            if attempt==2:raise RuntimeError('bounded range transfer failed') from None
    raise RuntimeError('range transfer incomplete')

print('resuming suffix bytes',meta.size-prefix,'from prefix',prefix,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    chunks=list(pool.map(fetch,range(6)))
out=root/(filename+'.assembled')
hash=hashlib.sha256()
with out.open('wb') as target, incomplete.open('rb') as source:
    left=prefix
    while left:
        data=source.read(min(left,8*1024*1024))
        if not data:raise RuntimeError('prefix changed')
        target.write(data);hash.update(data);left-=len(data)
    for path,size in chunks:
        if not size:continue
        with path.open('rb') as source:
            for data in iter(lambda:source.read(8*1024*1024),b''):
                target.write(data);hash.update(data)
if out.stat().st_size!=meta.size or hash.hexdigest()!=meta.etag.strip('"'):
    raise RuntimeError('assembled checkpoint checksum failed')
# Stop only this installer's original single-stream downloader after success.
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        if proc.stat().st_uid!=os.getuid():continue
        args=(proc/'cmdline').read_bytes().split(b'\0')
        args=[a for a in args if a]
        if len(args)==2 and args[-1].endswith(b'/download_step1x.py'):
            os.kill(int(proc.name),signal.SIGTERM)
    except (OSError,ProcessLookupError):pass
time.sleep(1)
out.replace(root/filename)
(root/'.cache/huggingface/download'/f'{filename}.metadata').write_text(f'{revision}\n{meta.etag.strip(chr(34))}\n{time.time()}\n')
(root/'.pinned-revision').write_text(revision+'\n')
print('checkpoint verified',meta.size,hash.hexdigest(),flush=True)
