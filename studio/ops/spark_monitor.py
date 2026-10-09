"""The work on this machine's chip, as the Spark's terminal monitor sees it, for the class page's console.

The console and the monitor used to work it out separately and disagreed: the console said
a video service was resting after "last took 11m 17s" — the last clip that *finished*, two days old for
3D — while the monitor showed the latest clip cancelled after 17 min 41 s; and the console knew
nothing of the models kept loaded, Blender or test runs, which is where most of the memory had gone. So
the console now asks the monitor's own code, `deploy/spark/dashboard_jobs.py`, and shows what it says.

That code reads Docker, the chip, the recorder's files in ~/monitor and the media services' job list,
all of it read-only. Where none of those exist (a development machine) it finds nothing, and says so as
an empty list rather than an error. The answer is cached because the panel polls every two seconds from
every page that has it open, and a refresh reads two days of the recorder's samples. After the first one,
a refresh runs beside the request, never in it: each Docker question may take up to five seconds, the
panel gives up on the whole answer after five, and a slow Docker must cost the chip list its freshness,
not the whole console its figures.
"""
import importlib.util
import threading
import time
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / 'deploy' / 'spark' / 'dashboard_jobs.py'
REFRESH_S = 5.0

_lock = threading.Lock()
_cached: tuple[float, dict | None] | None = None
_module = None


def monitor():
    """The monitor's module, loaded from its file once: it is a script beside its screen, not a package."""
    global _module
    if _module is None:
        spec = importlib.util.spec_from_file_location('dashboard_jobs', SOURCE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _module = module
    return _module


def refresh():
    """Read the monitor once and keep the answer, stamped when it was read; the caller holds `_lock`."""
    global _cached
    try:
        answer = monitor().picture()
    except Exception:        # a monitor that cannot read is a gap in the panel, never a broken console
        answer = None
    _cached = (time.time(), answer)


def refresh_and_release():
    try:
        refresh()
    finally:
        _lock.release()


def picture() -> dict | None:
    """What is on the chip now, what finished lately and today's totals; None when it could not be read.

    The first caller waits for the first reading. After that every caller gets the last one at once, and
    one older than REFRESH_S starts a new reading in the background, if none is already under way.
    """
    if _cached is None:
        with _lock:
            if _cached is None:
                refresh()
    elif time.time() - _cached[0] >= REFRESH_S and _lock.acquire(blocking=False):
        threading.Thread(target=refresh_and_release, daemon=True).start()
    return _cached[1] if _cached else None
