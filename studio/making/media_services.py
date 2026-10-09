"""What the media services on this machine are making right now, whoever asked them for it.

The console panel knows the requests of the class page in front of it and nothing else. Once
a teacher watched it report an idle studio while a video clip had been rendering for
ten minutes: the class that started that clip had ended, which drops its request from the panel
(`Classroom.end`), and the service carried on to the finish as it always does. The machine's own
terminal monitor showed the chip at 96% the whole time.

Each media service already answers `GET /v1/models` with the model it holds and whether it is busy,
and answers it on a second thread while the first is generating. This asks the services the running
deployment points at, so the panel can say which are working, resting or not answering. The answers
are cached because the panel polls every two seconds, from every page that is open, while the chip is
working.

How long a job has run and how the last one ended come from the Spark's own monitor
(`studio/ops/spark_monitor.py`), not from here. This used to offer the service's receipt of its last
*finished* job, which the console printed as "last took": after a cancelled clip it named one two
days old, beside a monitor that showed the cancellation.
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import urllib.error
import urllib.request

from studio.core.slots import load_profile

# The providers that mean "a service on this machine", from deployments.component_identity.
LOCAL_PROVIDERS = frozenset({'localimage', 'localmesh', 'localvideo', 'remotevoice', 'whispercpp'})
REFRESH_S = 5.0
TIMEOUT_S = 2.0
RESTING = {'standby', 'unavailable', ''}

_lock = threading.Lock()
_cached: dict[str, tuple[float, list]] = {}


def endpoints(deployment: str) -> dict[str, list[str]]:
    """Every media service on this machine the deployment points at, with the slots it serves."""
    found: dict[str, list[str]] = {}
    try:
        slots = load_profile(deployment)
    except Exception:            # an unknown or legacy selection names no services
        return found
    for name, config in slots.items():
        url = config.options.get('base_url')
        if config.provider in LOCAL_PROVIDERS and isinstance(url, str) and url.strip():
            found.setdefault(url.strip().rstrip('/'), []).append(name)
    return found


def ask(url: str) -> dict:
    request = urllib.request.Request(url + '/v1/models', headers={'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:
        return json.loads(answer.read(64 * 1024))


def reading(url: str, slots: list[str]) -> dict:
    row = {'url': url, 'slots': sorted(slots), 'answering': False, 'busy': None, 'model': None, 'phase': None}
    try:
        payload = ask(url)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return row
    models = payload.get('data') if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return row
    rows = [m for m in models if isinstance(m, dict)]
    working = next((m for m in rows if str(m.get('state', '')) not in RESTING), None)
    resting = next((m for m in rows if m.get('ready')), rows[0] if rows else None)
    holder = working or resting or {}
    row.update(answering=True, busy=bool(payload.get('busy')), model=str(holder.get('id', '')) or None,
               phase=str(working.get('state', '')) if working else 'standby')
    return row


def snapshot(deployment: str | None) -> list[dict]:
    """The services, refreshed at most every REFRESH_S; a caller during a refresh gets the last one."""
    if not deployment:
        return []
    at = time.time()
    fresh = _cached.get(deployment)
    if fresh and at - fresh[0] < REFRESH_S:
        return fresh[1]
    if not _lock.acquire(blocking=False):
        return fresh[1] if fresh else []
    try:
        services = sorted(endpoints(deployment).items())
        if not services:
            _cached[deployment] = (at, [])
            return []
        # Asked together, so a refresh costs one TIMEOUT_S however many services are wedged: the
        # panel's own fetch gives up after five seconds, and asking four in turn could outlast it.
        with ThreadPoolExecutor(max_workers=len(services)) as pool:
            rows = list(pool.map(lambda service: reading(*service), services))
        _cached[deployment] = (at, rows)
        return rows
    finally:
        _lock.release()
