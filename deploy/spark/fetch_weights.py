"""Fetch one ModelScope model onto the Spark at a capped speed, resuming where it stopped.

Why this exists instead of `modelscope download`: as measured, an
uncapped download filled the node's line (about 12 MB/s, roughly 100 Mbit/s),
and the organisers' frp relay, which carries every ssh login, upload and
tunnelled page view to the node, then lost about a third of its packets. With
the download paused the relay lost none and a 5 MB upload took 13 s instead of
failing at 5 KB/s. The CLI can only change how many files it fetches at once,
not how fast, so this caps the rate itself and leaves the rest of the line to
the relay.

Uses ModelScope's own file list and download links from the `modelscope`
package in ~/tools. A file already the right size is skipped; a partial one is
continued with a Range request. `.complete` is written when every file is in.

usage: ~/tools/bin/python fetch_weights.py MODEL_ID LOCAL_DIR [--rate MB/s] [--include GLOB ...]
"""
import argparse
import fnmatch
import time
import urllib.request
from pathlib import Path

from modelscope.hub.api import HubApi
from modelscope.hub.file_download import get_file_download_url

CHUNK = 256 * 1024


def fetch(url: str, target: Path, size: int, rate: float) -> None:
    """Stream url into target from wherever it stopped, never faster than rate bytes/s."""
    part = target.with_name(target.name + '.part')
    have = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={'Range': f'bytes={have}-'} if have else {})
    with urllib.request.urlopen(request, timeout=60) as response, part.open('ab' if have else 'wb') as out:
        if have and response.status != 206:
            out.truncate(0)
            have = 0
        started, sent = time.monotonic(), 0
        while chunk := response.read(CHUNK):
            out.write(chunk)
            sent += len(chunk)
            ahead = sent / rate - (time.monotonic() - started)
            if ahead > 0:
                time.sleep(ahead)
    if part.stat().st_size != size:
        raise OSError(f'{target.name}: {part.stat().st_size} of {size} bytes')
    part.rename(target)


def run(model_id: str, local_dir: Path, patterns=('*',), rate: float = 6.0) -> None:
    """Every file of model_id matching patterns into local_dir, at no more than rate MB/s."""
    files = [f for f in HubApi().get_model_files(model_id, recursive=True)
             if f.get('Size') and any(fnmatch.fnmatch(f['Path'], pattern) for pattern in patterns)]
    if not files:
        raise SystemExit(f'{model_id}: nothing matches {list(patterns)}')
    total = sum(f['Size'] for f in files)
    print(f'{model_id}: {len(files)} files, {total / 1e9:.1f} GB, cap {rate} MB/s', flush=True)
    for entry in files:
        target = local_dir / entry['Path']
        if target.exists() and target.stat().st_size == entry['Size']:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, 6):
            try:
                url = get_file_download_url(model_id, entry['Path'], 'master')
                fetch(url, target, entry['Size'], rate * 1e6)
                print(f'  got {entry["Path"]} ({entry["Size"] / 1e9:.2f} GB)', flush=True)
                break
            except OSError as error:
                print(f'  retry {attempt} {entry["Path"]}: {error}', flush=True)
                time.sleep(10 * attempt)
        else:
            raise SystemExit(f'{entry["Path"]} did not arrive')
    (local_dir / '.complete').touch()
    print(f'{model_id}: complete', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('model_id')
    parser.add_argument('local_dir', type=Path)
    parser.add_argument('--rate', type=float, default=6.0, help='MB/s cap (default 6, half the line)')
    parser.add_argument('--include', nargs='+', default=['*'], help='only paths matching these globs')
    args = parser.parse_args()
    run(args.model_id, args.local_dir, args.include, args.rate)


if __name__ == '__main__':
    main()
