"""The showpiece exhibit: one process on its own port, serving the temple dashboard.

What the routes DO lives in `routes.py`, because the classroom
server on 7060 serves the same showpiece and there must be one copy of it. What
is left here is this server: its socket, its route table, and the driver, page
and models the routes reach through `_exhibit`.

The exhibit is no longer the only way to see the temple, but it is still the one
the presenter script links to, and it is deliberately unchanged in what it
answers. Keeping it is also the fallback: if the merged page misbehaves, this
port still works on its own.

Every file the page fetches is resolved under the run's own folder and refused otherwise.
"""
from __future__ import annotations

import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from studio.showpiece.driver import Driver
from studio.showpiece.models import export_in_background
from studio.showpiece.routes import LOCAL_HOSTS, PAGE, TYPES, ShowpieceRoutes

# Re-exported: `gpu_stats` and `machine_stats` read this machine rather than any
# run, and moved to routes.py with the handler that calls them. Named here too so
# the exhibit's own tests and anything else that knew where they were still find
# them -- a pointer, not a second copy.
from studio.showpiece.routes import gpu_stats, machine_stats, showpiece_of, toy_model  # noqa: F401


class Exhibit(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, driver: Driver, page: Path) -> None:
        super().__init__(address, Handler)
        self.driver, self.page = driver, page
        self.models_root = driver.runs_root / "models"
        export_in_background(driver.model_path, self.models_root)


class Handler(ShowpieceRoutes, BaseHTTPRequestHandler):
    ROUTES = [
        ("GET", r"/", "showpiece_page"),
        ("GET", r"/harness", "harness"),
        ("GET", r"/(rebuild\.html|rebuild\.css|rebuild(?:-model|-hall|-scenes|-hood|-runs|-gloss|-marks|-compare)?\.mjs|rebuild(?:-run\d|-design\d+|-real)?-(?:record|hall|strings)\.json|rebuild-designs\.json|rebuild-[\w-]+\.(?:jpg|webp|mp4|glb|gz))", "showpiece_asset"),
        ("GET", r"/(app\.js|style\.css|timeline\.mjs|stream\.mjs|player\.mjs|screen\.mjs|plans\.mjs|viewer\.mjs|flow\.mjs|console\.mjs|ops\.mjs|strings\.json"
                r"|harness\.js|harness\.css|harnessplay\.mjs|harnessboard\.mjs|harness-roster\.json|harness-journeys\.json|harness-strings\.json)", "showpiece_asset"),
        ("GET", r"/vendor/((?:[\w-]+/)?[\w.-]+\.js)", "vendor"),
        ("GET", r"/api/models/([\w.-]+\.glb)", "model"),
        ("GET", r"/api/runs", "runs"),
        ("POST", r"/api/runs", "start"),
        ("GET", r"/api/runs/([^/]+)/events", "showpiece_events"),
        ("GET", r"/api/runs/([^/]+)/files/(.+)", "file"),
        ("GET", r"/api/stats", "stats"),
    ]

    @property
    def _exhibit(self):
        """Where this handler's driver, page and models are: on the exhibit, the
        server itself. The classroom supplies an object instead -- see routes.py."""
        return self.server

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        from studio.server.console_panel import serve_console
        if serve_console(self):
            return
        self._route("GET")

    def do_POST(self) -> None:
        self._route("POST")

    def _route(self, method: str) -> None:
        path = self.path.split("?", 1)[0]
        # Withholding the cross-origin answer (_cors) does not stop a page elsewhere from sending a plain POST that
        # starts a run; only this machine's pages may, as only the classroom's own page may on 7060 (code review).
        # A request with no Origin, a script or the presenter's curl, is not a browser page's.
        # "null", a sandboxed frame's, has no host at all and is refused with the rest.
        sent = self.headers.get("Origin")
        origin = urlsplit(sent or "")
        if method != "GET" and sent and origin.netloc != self.headers.get("Host") \
                and origin.hostname not in LOCAL_HOSTS:
            self._json(403, {"error": "Start a run from the showpiece page on this machine."})
            return
        for verb, pattern, name in self.ROUTES:
            match = re.fullmatch(pattern, path)
            if verb == method and match:
                try:
                    getattr(self, f"_{name}")(*match.groups())
                except ValueError as error:      # a body too large or not JSON: 400, as the classroom's _route answers
                    self._json(400, {"error": str(error), "code": getattr(error, "code", "bad_request")})
                return
        self._json(404, {"error": f"no route for {method} {path}"})

    def _harness(self) -> None:
        """The second page: the harness view, a conceptual animation fed by checked data, not a run."""
        self._bytes(200, (self.server.page / "harness.html").read_bytes(), TYPES[".html"])

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()


def make_server(port: int, driver: Driver, page: Path = PAGE) -> Exhibit:
    return Exhibit(("127.0.0.1", port), driver, page)
