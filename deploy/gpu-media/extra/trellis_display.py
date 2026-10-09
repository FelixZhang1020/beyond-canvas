"""Run the pinned legacy viewer with its GPU actions sharing the media lock."""
import fcntl
import sys
sys.path.insert(0, "/app")
from functools import wraps
from pathlib import Path


def serialized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with open('/worker/gpu.lock', 'a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return function(*args, **kwargs)
    return wrapped


source = Path('/app/app.py').read_text()
for name in ('image_to_3d', 'extract_glb'):
    marker = '\ndef ' + name + '('
    if source.count(marker) != 1:
        raise RuntimeError('pinned legacy viewer signature changed')
    source = source.replace(marker, '\n@serialized' + marker, 1)
exec(compile(source, '/app/app.py', 'exec'), {'__name__': '__main__', '__file__': '/app/app.py', 'serialized': serialized})
