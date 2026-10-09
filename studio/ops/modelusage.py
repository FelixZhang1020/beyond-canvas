"""What a loaded model is actually costing: which file, how much disk, how much memory.

Everything here is measured from the process holding the port, never from a
profile. That distinction is the whole point. A profile says which model was
meant to be there; this says which file is open right now, which is the only
version worth showing on a board whose job is to be believed.

It degrades rather than guesses. `lsof` is how the process behind a port is
found and it is not on every machine, so anything unavailable comes back as
None and the board says "not known" instead of printing a zero. A zero is a
measurement and None is an absence, and confusing the two on a page about
memory would be the kind of quiet lie this board exists to avoid.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

BYTES_IN_GB = 1024 ** 3

# llama.cpp takes the weights with -m and the vision projector with --mmproj,
# and both are real files on disk. whisper-server takes only -m. Counting the
# projector matters: it is 3.7 GB, nearly as large as the weights it serves.
PATH_FLAGS = ("-m", "--model", "--mmproj")


def _run(command: list[str], timeout: float = 2.0) -> str:
    """Run a short read-only command, returning "" rather than raising."""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout if done.returncode == 0 else ""


def _serving_argv(port: int) -> tuple[list[str], int] | None:
    """The command line and pid of whatever is listening on this port.

    Returns None when nothing is listening or when `lsof` is unavailable, which
    is a real possibility on a stripped Linux image such as the Spark.
    """
    listed = _run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"]).split()
    if not listed:
        return None
    try:
        pid = int(listed[0])
    except ValueError:
        return None
    argv = _run(["ps", "-ww", "-o", "command=", "-p", str(pid)]).strip()
    return (argv.split(), pid) if argv else None


def _bytes_on_disk(path: str) -> int | None:
    """The real size of a file, following symlinks into the model caches."""
    try:
        return Path(path).resolve().stat().st_size
    except OSError:
        return None


def _resident_bytes(pid: int) -> int | None:
    """Resident set of a process, in bytes.

    This UNDERSTATES a memory-mapped model, and the board says so rather than
    dressing the number up. llama.cpp maps the weights, so the pages are shared
    with the file cache and are charged to the process only once touched; on
    Metal a further share sits in memory the GPU and CPU both address. The
    honest reading is "at least this much", which is still the number that tells
    you whether a second model will fit.
    """
    out = _run(["ps", "-o", "rss=", "-p", str(pid)]).strip()
    try:
        return int(out) * 1024  # ps reports kilobytes
    except ValueError:
        return None


def model_paths(argv: list[str]) -> list[str]:
    """Every model file named on a server's command line, in the order given."""
    return [
        argv[index + 1]
        for index, token in enumerate(argv[:-1])
        if token in PATH_FLAGS
    ]


def usage_for(port: int) -> tuple[list[str], float | None, float | None]:
    """(paths, disk in GB, resident memory in GB) for whatever holds this port.

    Any part that cannot be measured comes back None, and the parts that can
    still do. A model whose path is readable but whose size is not is more
    useful than nothing at all.
    """
    found = _serving_argv(port)
    if found is None:
        return [], None, None
    argv, pid = found
    paths = model_paths(argv)

    sizes = [size for size in (_bytes_on_disk(path) for path in paths) if size]
    disk_gb = round(sum(sizes) / BYTES_IN_GB, 2) if sizes else None

    resident = _resident_bytes(pid)
    ram_gb = round(resident / BYTES_IN_GB, 2) if resident else None
    return paths, disk_gb, ram_gb


def probe(url: str, timeout: float = 0.6) -> str | None:
    """Ask a server what it is serving. None means nothing answered at all.

    Tries the model list first, because a name is more useful than a tick, then
    the two places a tick lives: /health for a llama.cpp-style server, and
    /api/health for the studio page, which the page contract settles. The
    last of those used to be missing, so the board called a running
    studio page down — the one service on the board a teacher actually opens.
    """
    for path, name_expected in (("/v1/models", True), ("/health", False), ("/api/health", False)):
        try:
            with urllib.request.urlopen(url + path, timeout=timeout) as response:
                body = response.read(4096).decode("utf-8", "replace")
        except (urllib.error.URLError, OSError, ValueError):
            continue
        if not name_expected:
            return "up"
        try:
            parsed = json.loads(body)
            models = parsed.get("models") or parsed.get("data") or []
            name = (models[0].get("model") or models[0].get("id") or "") if models else ""
            return Path(name).name or "up"
        except (json.JSONDecodeError, AttributeError, IndexError, TypeError):
            return "up"
    return None
