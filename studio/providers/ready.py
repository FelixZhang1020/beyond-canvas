"""Whether a model on this machine answers again after stepping aside for a job's memory.

On the Spark a clip pauses the kept-loaded models it needs room from (deploy/spark/media_spark.py
room_for) and lets them load again once it is done: NVIDIA's safety reader and Qwen, the screener.
Both answer `/health` only once loaded, so a look that follows the clip asks that address until it
says yes. One loop for both clients, so the two waits cannot drift apart.
"""

from __future__ import annotations

import time

import httpx


def back_within(http: httpx.Client, base_url: str, seconds: float, pause: float = 2.0) -> bool:
    """Whether `base_url/health` answers 200, asking until `seconds` pass; zero asks once and never sleeps."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            if http.get(f"{base_url}/health", timeout=2.0).status_code == 200:
                return True
        except httpx.RequestError:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(pause)
