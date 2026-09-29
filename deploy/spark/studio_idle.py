"""Refuse a studio restart until its accepted requests have finished saving."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from studio.server.serve_door import COOKIE, Door


def idle(health: dict) -> bool:
    count = health.get("active_requests")
    return isinstance(count, int) and not isinstance(count, bool) and count == 0


def main() -> int:
    try:
        door = Door(Path.home() / ".config/beyond-canvas/door")
        request = Request("http://127.0.0.1:7060/api/health",
                          headers={"Cookie": f"{COOKIE}={door.cookie()}"})
        with urlopen(request, timeout=3) as response:
            health = json.load(response)
    except URLError as error:
        # A stopped studio has no work to interrupt and is exactly what restart.sh repairs.
        return 0 if isinstance(error.reason, ConnectionRefusedError) else 3
    except (OSError, ValueError):
        return 3
    return 0 if isinstance(health, dict) and idle(health) else 3


if __name__ == "__main__":
    sys.exit(main())
