"""Serve the studio page and the harness behind it, on one port, on the box.

Standard library only. The Spark will run this, and every dependency is one
more thing to build on ARM; the page is one file beside two photographs and its logo,
the routes are 55, and threads are enough for one classroom. That count said seven from the day it was
written until it was off by thirty-one; it is pinned
now by `test_the_route_count_in_the_docstring_is_the_real_one`, because a number
in prose that nothing checks is a claim, not a fact. It earned its keep within
the hour, catching this sentence the moment the showpiece added ten routes.

The route table below is the whole map of this server, but not the whole of its
code: the bodies for course history, speaking and the status board live in
`serve_portfolio.py`, `serve_speech.py` and `serve_board.py`, and the temple
showpiece's in `studio/showpiece/routes.py`, all mixed into the handler. The
first three left when this file passed the 500-line limit the size
guard refuses writes over; the showpiece is shared with the exhibit on 7090,
which serves the same routes from the same code.

Routes follow docs/specs/studio-page-contract.md. One
addition the contract does not yet name: a run that stops sends its stopped
event and then a `done` event carrying the same status, because the page closes
its event stream only on `done`, and an unannounced close would make it report a
model outage over the top of a kind refusal.

    uv run python -m studio.serve            # http://127.0.0.1:7060/

Port 7060 avoids both the old 8080 model collision and macOS Control Center's
AirPlay listener on 7000. The convention is in tests/server/test_ports.py, which fails
if anything moves back on top of a model.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, parse_qs
import sqlite3

from studio.classroom.classroom import Classroom
from studio.core.env import load_dotenv
from studio.core.errors import ModelError
from studio.classroom.samples import SampleLibrary
from studio.classroom.portfolio import Portfolio, CourseClosed
from studio.server.page_transfer import PageRoutes
from studio.server.ports import HIGH, LOW, PAGE_PORT, off_convention, spare_port
from studio.server.serve_board import BoardRoutes
from studio.server.serve_door import Door, DoorRoutes
from studio.server.serve_portfolio import PortfolioRoutes
from studio.server.serve_showpiece import ShowpieceHolder, ShowpieceMount
from studio.server.serve_speech import SpeechRoutes
from studio.server.uploads import parse_multipart, read_body

# How long a request stream may stay silent before the page hears a comment
# line. A video stage sits for minutes with nothing to report, and the speech
# route measured a browser giving up on a silent connection at ~7.8 s. Read at
# call time so a test can shorten it.
KEEP_ALIVE_S = 2.0

PAGE = Path(__file__).with_name("page") / "index.html"
DEFAULT_LEDGER = Path(".studio") / "ledger.jsonl"


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, classroom: Classroom, page: Path = PAGE) -> None:
        super().__init__(address, StudioHandler)
        self.classroom = classroom
        self.page = page
        self.samples = SampleLibrary()
        self.door = Door.from_env()  # the Spark's password; None everywhere else (serve_door.py)
        # Nothing of the temple is built here: the holder makes its driver, its
        # model client and its GLB export on the first /showpiece request, so a
        # class that never opens one pays nothing for it.
        self.showpiece = ShowpieceHolder()

    def handle_error(self, request, client_address) -> None:
        """Report a broken request, unless reporting is itself what broke."""
        try:
            super().handle_error(request, client_address)
        except OSError:
            pass  # The stream this would be written to has no reader left.


class StudioHandler(DoorRoutes, PageRoutes, PortfolioRoutes, SpeechRoutes, BoardRoutes, ShowpieceMount,
                    BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: StudioServer

    ROUTES = (
        ("GET", r"/", "page"),
        ("GET", r"/index\.html", "page"),
        ("GET", r"/assets/entrance/([\w-]+\.jpg)", "entrance"),
        ("GET", r"/assets/brand/([\w-]+\.(?:png|ico))", "brand"),
        ("GET", r"/showpiece", "showpiece_redirect"),
        ("GET", r"/showpiece/", "showpiece_page"),
        ("GET", r"/showpiece/vendor/((?:[\w-]+/)?[\w.-]+\.js)", "vendor"),
        ("GET", r"/showpiece/api/stats", "stats"),
        ("GET", r"/showpiece/api/runs", "runs"),
        ("POST", r"/showpiece/api/runs", "start"),
        ("GET", r"/showpiece/api/runs/([^/]+)/events", "showpiece_events"),
        ("GET", r"/showpiece/api/runs/([^/]+)/files/(.+)", "file"),
        ("GET", r"/showpiece/api/models/([\w.-]+\.glb)", "model"),
        ("GET", r"/showpiece/([\w.-]+\.(?:js|mjs|css|json|html|jpg|webp|mp4|glb|gz))", "showpiece_asset"),
        ("GET", r"/harness", "harness_redirect"),
        ("GET", r"/harness/(.*)", "harness"),
        ("GET", r"/showcase/3d", "showcase_redirect"),
        ("GET", r"/showcase/3d/(.*)", "showcase"),
        ("GET", r"/viewer/3d/(.*)", "showcase"),
        ("GET", r"/api/health", "health"),
        ("GET", r"/api/deployments", "deployments"),
        ("POST", r"/api/deployments", "select_deployment"),
        ("POST", r"/api/deployments/check", "check_deployment"),
        ("GET", r"/api/courses", "courses"),
        ("GET", r"/api/courses/([^/]+)", "course"),
        ("PATCH", r"/api/courses/([^/]+)", "rename_course"),
        ("POST", r"/api/courses/([^/]+)/complete", "complete_course"),
        ("DELETE", r"/api/courses/([^/]+)", "delete_course"),
        ("POST", r"/api/courses/([^/]+)/reopen", "reopen_course"),
        ("POST", r"/api/courses/([^/]+)/edit", "edit_course"),
        ("GET", r"/api/courses/([^/]+)/drawings/([^/]+)", "course_drawing"),
        ("GET", r"/api/courses/([^/]+)/activities/([^/]+)", "course_activity"),
        ("GET", r"/api/courses/([^/]+)/activities/([^/]+)/media/([\w.]+)", "course_media"),
        ("POST", r"/api/courses/([^/]+)/speech", "course_speech"),
        ("PATCH", r"/api/courses/([^/]+)/activities/([^/]+)/(ending|view)", "course_result"),
        ("GET", r"/board", "board"),
        ("GET", r"/api/lights", "lights"),
        ("GET", r"/api/prompts", "prompts"),
        ("POST", r"/api/session", "begin"),
        ("DELETE", r"/api/session/([^/]+)", "end"),
        ("PATCH", r"/api/session/([^/]+)/drafts", "drafts"),
        ("PATCH", r"/api/session/([^/]+)", "settings"),
        ("POST", r"/api/session/([^/]+)/speech", "speech"),
        ("DELETE", r"/api/session/([^/]+)/speech", "stop_speech"),
        ("POST", r"/api/session/([^/]+)/drawings", "add_drawing"),
        ("GET", r"/api/session/([^/]+)/samples", "samples"),
        ("GET", r"/api/session/([^/]+)/samples/([a-f0-9]+)", "sample"),
        ("GET", r"/api/session/([^/]+)/drawings/([^/]+)", "drawing"),
        ("DELETE", r"/api/session/([^/]+)/drawings/([^/]+)", "remove_drawing"),
        ("DELETE", r"/api/session/([^/]+)/drawings/([^/]+)/(conversation|last-round)", "forget_chat"),
        ("POST", r"/api/session/([^/]+)/heard", "heard"),
        ("POST", r"/api/session/([^/]+)/requests", "request"),
        ("DELETE", r"/api/session/([^/]+)/requests/([^/]+)", "cancel"),
        ("GET", r"/api/requests/([^/]+)/events", "events"),
        ("GET", r"/api/session/([^/]+)/ledger", "ledger"),
    )

    # Dispatch ----------------------------------------------------------------

    def do_GET(self) -> None:
        from studio.server.console_panel import serve_console
        if self._door_shut(): return
        if serve_console(self):
            return
        self._route("GET")

    def do_POST(self) -> None:
        self._route("POST")

    def do_DELETE(self) -> None:
        self._route("DELETE")

    def do_PATCH(self) -> None:
        self._route("PATCH")

    def _route(self, method: str) -> None:
        if self._door_shut(): return
        origin = self.headers.get("Origin")
        if method != "GET" and origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self._json(403, {"error": "Use the classroom page on this server."})
            return
        path = urlsplit(self.path).path
        for verb, pattern, name in self.ROUTES:
            match = re.fullmatch(pattern, path)
            if verb == method and match:
                try:
                    getattr(self, f"_{name}")(*match.groups())
                except KeyError as error:
                    # `code` tells one 404 from another: a lost editing session (SessionGone) is
                    # the page's to rejoin, not the teacher's to retype.
                    self._json(404, {"error": str(error), "code": getattr(error, "code", "not_found")})
                except CourseClosed as error:
                    self._json(409, {"error": str(error), "code": "course_closed"})
                except ValueError as error:
                    self._json(400, {"error": str(error), "code": getattr(error, "code", "bad_request")})
                except (sqlite3.Error, OSError):
                    self._json(503, {"error": "Course storage is unavailable. Please retry."})
                return
        self._json(404, {"error": f"no route for {method} {path}"})

    def log_message(self, format: str, *args: Any) -> None:
        """Say what was asked for, and never let saying it cost the reply.

        A studio started detached outlives its launcher, and when the launcher
        goes so does the reader of this stream. The write then fails, and it
        fails BEFORE the first byte of the reply, so the port stays open while
        every request dies unanswered and the page waits for ever. Measured
        after a five-minute video was blamed for it.
        """
        try:
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))
        except OSError:
            pass  # Nobody is reading. The class carries on without a record.

    # Replies -----------------------------------------------------------------

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._bytes(status, body, "application/json; charset=utf-8")

    def _bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _body(self) -> bytes:
        return read_body(self)  # refused unread past its limit (studio/server/uploads.py)

    def _json_body(self) -> dict[str, Any]:
        body = self._body()
        if not body:
            return {}
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
        return payload

    # Routes ------------------------------------------------------------------

    def _deployments(self):
        result = self.server.classroom.deployment_status()
        sid = parse_qs(urlsplit(self.path).query).get('session_id', [''])[0]
        if sid:
            result['session'] = self.server.classroom.session_capabilities(sid)
        self._json(200, result)

    def _check_deployment(self):
        from studio.core.deployment_checks import check_deployment
        self._json(200, check_deployment(self.server.classroom, self._json_body().get('deployment')))

    def _select_deployment(self):
        payload = self._json_body()
        from studio.core.deployment_checks import check_deployment
        check = check_deployment(self.server.classroom, payload.get('deployment'))
        if not check['ready']:
            self._json(200, dict(self.server.classroom.deployment_status(), switched=False, check=check))
            return
        try:
            result = self.server.classroom.switch_deployment(payload.get('deployment'))
            result.update(switched=True, check=check)
        except ModelError:
            self._json(503, {'error': 'Deployment could not be configured. Current selection is unchanged.'})
            return
        self._json(200, result)

    def _health(self) -> None:
        self._json(200, self.server.classroom.health())

    def _harness_redirect(self) -> None:
        """`/harness` without the slash. The page's stylesheets, its two module
        imports and its three JSON fetches are all relative, so they only resolve
        from `/harness/`; landing on the bare path would serve the HTML and then
        404 every file in it."""
        self.send_response(302)
        self.send_header('Location', '/harness/')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _harness(self, route: str) -> None:
        from studio.server.serve_harness import send_file
        send_file(self, route)

    def _showcase_redirect(self) -> None:
        self.send_response(302)
        self.send_header('Location', '/showcase/3d/')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _showcase(self, route: str) -> None:
        from studio.showcase_3d.serve import send_file
        send_file(self, route)

    def _begin(self) -> None:
        session_id = self.server.classroom.begin(self._json_body())
        self._json(200, {"session_id": session_id, "course_id": session_id,
                         "capabilities": self.server.classroom.session_capabilities(session_id)})

    def _end(self, session_id: str) -> None:
        self.server.classroom.end(session_id)
        self._bytes(204, b"", "application/json")  # Releasing an already-closed editor is harmless.

    def _drafts(self, session_id):
        self.server.classroom.save_drafts(session_id, self._json_body().get("drafts"))
        self._bytes(204, b"", "application/json")

    def _settings(self, session_id):
        self.server.classroom.update_settings(session_id, self._json_body())
        self._bytes(204, b"", "application/json")

    def _add_drawing(self, session_id: str) -> None:
        fields = parse_multipart(self.headers.get("Content-Type", ""), self._body())
        if "image" not in fields:
            raise ValueError("multipart field 'image' is required")
        drawing_id = self.server.classroom.add_drawing(session_id, fields["image"])
        url = f"/api/session/{session_id}/drawings/{drawing_id}"
        self._json(200, {"drawing_id": drawing_id, "url": url})

    def _drawing(self, session_id: str, drawing_id: str) -> None:
        data, content_type = self.server.classroom.drawing(session_id, drawing_id)
        self._bytes(200, data, content_type)

    def _samples(self, session_id):
        session = self.server.classroom._session(session_id)
        items = []
        for sample_id in self.server.samples.files(session.entrance):
            url = f"/api/session/{session_id}/samples/{sample_id}"
            items.append({"id": sample_id, "url": url, "thumbnail_url": url + "?thumbnail=1"})
        self._json(200, {"items": items})

    def _sample(self, session_id, sample_id):
        session = self.server.classroom._session(session_id)
        thumbnail = urlsplit(self.path).query == "thumbnail=1"
        self._bytes(200, self.server.samples.image(session.entrance, sample_id, thumbnail), "image/jpeg")

    def _heard(self, session_id: str) -> None:
        """A recording in, a sentence out, and a handle the answer sends back to keep a first recording."""
        fields = parse_multipart(self.headers.get("Content-Type", ""), self._body())
        if "audio" not in fields:
            raise ValueError("multipart field 'audio' is required")
        try:
            heard = self.server.classroom.hear(session_id, fields["audio"])
        except ModelError as error:
            self.log_message("hearing failed: %s", error)  # a bare 503 hid why a class could not be heard
            self._json(503, {"error": str(error)})
            return
        self._json(200, {"text": heard.text, "language": heard.language, "sample": heard.sample})

    def _request(self, session_id: str) -> None:
        payload = self._json_body()
        drawing_ids = payload.get("drawing_ids") or []
        if not isinstance(drawing_ids, list):
            raise ValueError("drawing_ids must be a list")
        options = payload.get("options") or {}
        if not isinstance(options, dict):
            raise ValueError("options must be an object")
        started = self.server.classroom.request(
            session_id, str(payload.get("skill", "")), [str(d) for d in drawing_ids], options
        )
        self.server.classroom.start(started["request_id"])
        self._json(200, started)

    def _events(self, request_id: str) -> None:
        events = self.server.classroom.follow(request_id, quiet_after=KEEP_ALIVE_S)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        # SSE has a keepalive for a silent stage: a line starting with ":" that
        # EventSource is spec-required to ignore. The stream itself reports the
        # quiet, so this stays one loop on one thread with the socket's own
        # backpressure; a relay through a thread and a queue was reviewed
        # and not merged, because it could lose the last event.
        try:
            self.wfile.write(b": open\n\n")
            self.wfile.flush()
            for item in events:
                if item is None:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                name, data = item
                frame = f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                self.wfile.write(frame.encode("utf-8"))
                self.wfile.flush()
        except OSError:
            # The browser left. That is EPIPE or ECONNRESET on this Mac and
            # ETIMEDOUT on the Spark once the peer has vanished; none of them
            # deserves the 503 the dispatcher would send onto a socket that
            # already had its 200.
            pass
        self.close_connection = True

    def _cancel(self, session_id, request_id):
        self.server.classroom.cancel(session_id, request_id)
        self._bytes(204, b"", "application/json")

    def _ledger(self, session_id: str) -> None:
        self._json(200, {"lines": self.server.classroom.ledger_lines(session_id)})


def make_server(classroom: Classroom, host: str = "127.0.0.1", port: int = PAGE_PORT, page: Path = PAGE) -> StudioServer:
    return StudioServer((host, port), classroom, page)



# macOS AirPlay Receiver listens on *:5000 and *:7000. A loopback bind beats a
# wildcard one, so the teacher's own browser reaches the studio and nothing
# looks wrong; `--host 0.0.0.0` for a tablet is refused with errno 48 and no
# hint of why. Measured.
AIRPLAY_PORTS = (5000, 7000)


def _somewhere_else(port: int) -> int:
    """A free-looking port that still obeys the convention.

    It offered `--port 8442` for a busy 8412 — a remedy breaking the rule the
    same program had just warned about. Then it offered 7090 for
    a busy 7060: inside the band and ending in zero, and the exhibit's own port
    by then, so the remedy moved you onto a second server. The rule it
    has to obey is now kept in one place with the ports themselves.
    """
    return spare_port(port)


def why_busy(host: str, port: int, platform: str = sys.platform) -> str:
    """What is probably holding this address, and what to do about it."""
    elsewhere = f"Or serve it somewhere else: --port {_somewhere_else(port)}"
    if platform == "darwin" and port in AIRPLAY_PORTS and host not in ("127.0.0.1", "localhost"):
        return ("On a Mac this is AirPlay Receiver, which holds this port on every "
                "interface. Turn it off in System Settings > General > AirDrop & Handoff "
                f"to reach the studio from a tablet. {elsewhere}")
    return f"Something is already listening on {host}:{port}. {elsewhere}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve the studio page and the harness behind it")
    parser.add_argument("--host", default="127.0.0.1", help="bind address; 0.0.0.0 to reach it from a tablet")
    parser.add_argument("--port", type=int, default=PAGE_PORT)
    parser.add_argument("--profile", default="stepfun", help="which profile resolves the model slots")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER), help="append-only ledger; hashes, never content")
    parser.add_argument("--portfolio", default=".studio/portfolio.sqlite3", help="local course history database")
    parser.add_argument("--deployment", choices=("stepfun", "current"), default=None)
    parser.add_argument("--deployment-state", default=None, help="selection file; defaults beside the ledger")
    parser.add_argument("--speech-provider", choices=("none", "voxcpm", "stepfun"), default="none")
    candidates = Path(__file__).resolve().parents[1] / "scratch/voice-candidates"
    parser.add_argument("--voxcpm-path", default=str(candidates / "vox-model"))
    parser.add_argument("--voxcpm-source", default=str(candidates / "voxcpm/src"))
    parser.add_argument("--voxcpm-device", choices=("mps", "cuda", "cpu"), default="mps")
    arguments = parser.parse_args(argv)

    stray = off_convention(arguments.port)
    if stray:
        print(stray, file=sys.stderr)

    load_dotenv()
    classroom = Classroom(arguments.ledger, profile=arguments.profile, portfolio=Portfolio(arguments.portfolio))
    classroom.look_on_arrival = True   # the safety look runs as each photo arrives
    if arguments.speech_provider == "stepfun":
        from studio.providers.stepfun_voice import StepFunClassroomVoice
        classroom.voice = StepFunClassroomVoice()
    if arguments.speech_provider == "voxcpm":
        from studio.voice.speech import load_local_voice
        print("Loading and warming the local classroom voice…", flush=True)
        classroom.voice = load_local_voice(arguments.voxcpm_path, arguments.voxcpm_source, arguments.voxcpm_device)
    from studio.core.deployments import restore_selection
    restore_selection(classroom, arguments.deployment_state or Path(arguments.ledger).with_name("deployment.json"), arguments.deployment)
    try:
        server = make_server(classroom, arguments.host, arguments.port)
    except OSError as error:
        sys.exit(f"Cannot listen on {arguments.host}:{arguments.port}: {error}.\n"
                 f"{why_busy(arguments.host, arguments.port)}")
    # The classroom's own profile, not --profile, whose default is the constant
    # "stepfun" — so this line said StepFun First however the studio was started.
    print(f"Beyond Canvas studio on http://{arguments.host}:{arguments.port}/  profile={classroom.profile}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        classroom.close()
        runtime = getattr(getattr(classroom, "voice", None), "runtime", None)
        if runtime is not None:
            runtime.close()


if __name__ == "__main__":
    main()
