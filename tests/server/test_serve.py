"""The routes, driven over a real socket the way the page drives them.

The classroom tests hold the behaviour; these hold the wire. What can only go
wrong here: a route that does not exist, a multipart body the parser cannot
read, an event stream that closes before the page has heard why it stopped, and
a drawing still being served after the class has ended.
"""

import json
import sys
import threading
import urllib.error
import urllib.request
import uuid

import pytest

from studio.classroom.classroom import Classroom
from studio.serve import make_server, parse_multipart

DRAWING = "skills/art-feedback/evals/files/dog-sun.png"
CLASS = {"language": "en", "entrance": "colour"}

ALLOW = '{"verdict": "allow", "reason": "a drawing", "text_found": []}'
GOOD = (
    "I see a yellow sun with pointy triangle rays. I notice two figures below it. "
    "What is happening between them?"
)
GROUNDED = '{"grounded": ["yellow sun", "two figures"]}'
CLEAN = '{"presumptive": []}'


class Scripted:
    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.providers.base import ChatResult

        text = self.replies.pop(0) if self.replies else "{}"
        return ChatResult(
            text=text, input_tokens=10, output_tokens=10, reasoning_tokens=0,
            cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
        )


@pytest.fixture
def studio(tmp_path):
    """A server on an ephemeral port, torn down with the test."""
    client = Scripted([ALLOW, GOOD, GROUNDED, CLEAN])
    classroom = Classroom(
        tmp_path / "ledger.jsonl", clients={"vlm.studio": client, "vlm.director": client}
    )
    page = tmp_path / "index.html"
    page.write_text("<title>Beyond Canvas</title>", encoding="utf-8")
    server = make_server(classroom, "127.0.0.1", 0, page)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    classroom.close()


def call(base, method, path, body=None, content_type="application/json"):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    request = urllib.request.Request(base + path, data=data, method=method)
    if data:
        request.add_header("Content-Type", content_type)
    with urllib.request.urlopen(request, timeout=20) as reply:
        raw = reply.read()
        if reply.status == 204 or not raw:
            return reply.status, None
        if reply.headers.get_content_type() == "application/json":
            return reply.status, json.loads(raw)
        return reply.status, raw


def multipart(field, filename, payload):
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def stream(base, request_id):
    """Read the event stream to its end, as the page's EventSource does."""
    events = []
    with urllib.request.urlopen(base + f"/api/requests/{request_id}/events", timeout=30) as reply:
        name = None
        for raw in reply:
            line = raw.decode("utf-8").strip()
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: ") and name:
                events.append((name, json.loads(line[6:])))
    return events


def open_class(base, settings=None):
    _, started = call(base, "POST", "/api/session", settings or CLASS)
    return started["session_id"]


def add_drawing(base, session_id):
    body, content_type = multipart("image", "d.png", open(DRAWING, "rb").read())
    _, added = call(base, "POST", f"/api/session/{session_id}/drawings", body, content_type)
    return added["drawing_id"]


def test_the_page_is_served_from_the_same_port_as_the_harness(studio):
    """One port, so a tablet on the studio wifi needs one address and no build step."""
    status, body = call(studio, "GET", "/")
    assert status == 200
    assert b"Beyond Canvas" in body


def test_health_tells_the_page_which_profile_is_running(studio):
    _, health = call(studio, "GET", "/api/health")
    assert health["ok"] is True
    assert health["profile"] == "cloud"
    assert health["mode"] == "studio"


def test_health_names_the_skills_this_studio_can_actually_run(studio):
    """The page hides the controls for everything else, rather than offering a
    button that always answers "that part is not open yet"."""
    _, health = call(studio, "GET", "/api/health")
    assert "art-feedback" in health["skills"]
    assert "drawings-to-storybook" in health["skills"]
    assert "painting-to-scene" not in health["skills"]


def test_a_class_without_an_entrance_is_refused_with_a_reason(studio):
    with pytest.raises(urllib.error.HTTPError) as caught:
        call(studio, "POST", "/api/session", {"language": "en"})
    assert caught.value.code == 400
    assert "entrance" in json.loads(caught.value.read())["error"]


def test_one_drawing_through_the_whole_loop(studio):
    session_id = open_class(studio)
    drawing_id = add_drawing(studio, session_id)
    _, started = call(
        studio,
        "POST",
        f"/api/session/{session_id}/requests",
        {"skill": "art-feedback", "drawing_ids": [drawing_id], "options": {}},
    )
    assert [step["stage"] for step in started["plan"]] == [
        "studio-safety",
        "art-feedback",
        "rubric",
    ]
    events = stream(studio, started["request_id"])
    assert events[-1][0] == "done"
    outputs = events[-1][1]["outputs"]
    assert outputs["question"] == "What is happening between them?"
    steps = [data["stage"] for name, data in events if name == "stage"]
    assert steps[0] == "studio-safety", "safety is always first, and the page shows it"
    assert "rubric" in steps


def test_the_ledger_route_returns_what_the_stream_reported(studio):
    session_id = open_class(studio)
    drawing_id = add_drawing(studio, session_id)
    _, started = call(
        studio,
        "POST",
        f"/api/session/{session_id}/requests",
        {"skill": "art-feedback", "drawing_ids": [drawing_id], "options": {}},
    )
    stream(studio, started["request_id"])
    _, ledger = call(studio, "GET", f"/api/session/{session_id}/ledger")
    assert [line["stage"] for line in ledger["lines"]] == ["studio-safety", "art-feedback"]
    assert all(line["inputs_hash"] for line in ledger["lines"])


def test_ending_the_class_stops_the_drawing_being_served(studio):
    session_id = open_class(studio)
    drawing_id = add_drawing(studio, session_id)
    status, image = call(studio, "GET", f"/api/session/{session_id}/drawings/{drawing_id}")
    assert status == 200 and image[:4] == b"\x89PNG"
    assert call(studio, "DELETE", f"/api/session/{session_id}")[0] == 204
    with pytest.raises(urllib.error.HTTPError) as caught:
        call(studio, "GET", f"/api/session/{session_id}/drawings/{drawing_id}")
    assert caught.value.code == 404


def test_an_unknown_route_says_so_rather_than_hanging(studio):
    with pytest.raises(urllib.error.HTTPError) as caught:
        call(studio, "GET", "/api/nothing-here")
    assert caught.value.code == 404


class Unread:
    """A stream whose reader has gone, the way an orphaned server's pipe has."""

    def write(self, text):
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self):
        raise BrokenPipeError(32, "Broken pipe")


def test_a_request_survives_a_status_line_nobody_is_reading(studio, monkeypatch):
    """A lost status pipe must cost the line, never the reply.

    Measured: the studio was started detached, its launcher exited,
    and from then on every request died in the status line before a single byte
    of the reply was written. The port stayed open and the page waited for ever,
    so a working video read as a broken studio. Silence is the only acceptable
    failure for a status line.
    """
    monkeypatch.setattr(sys, "stderr", Unread())
    status, body = call(studio, "GET", "/api/health")
    assert status == 200
    assert body["ok"] is True


def test_reading_a_multipart_body():
    body, content_type = multipart("image", "d.png", b"\x89PNG-ish")
    assert parse_multipart(content_type, body) == {"image": b"\x89PNG-ish"}


def test_a_request_larger_than_the_studio_reads_is_refused_before_a_byte_of_it_is_read(studio):
    """One request must not hold the memory the whole class shares (code review). The
    studio answers from the declared length alone and closes the connection: the body is never sent
    here, so a studio that waited for it, or kept the connection open, runs this into its timeout."""
    import socket
    from urllib.parse import urlsplit
    from studio.server.uploads import MAX_BODY

    address = urlsplit(studio)
    for declared in (MAX_BODY + 1, -1, "twelve"):
        with socket.create_connection((address.hostname, address.port), timeout=5) as raw:
            raw.sendall(f"POST /api/session HTTP/1.1\r\nHost: {address.netloc}\r\n"
                        f"Content-Type: application/json\r\nContent-Length: {declared}\r\n\r\n".encode())
            reply = b""
            while chunk := raw.recv(65536):  # ends only when the studio closes the connection
                reply += chunk
        head, _, body = reply.partition(b"\r\n\r\n")
        assert head.startswith(b"HTTP/1.1 400") and json.loads(body)["code"] == "too_large"


def test_a_recording_becomes_a_sentence_the_teacher_can_read(studio, monkeypatch):
    """The route exists so the teacher confirms what was heard before it is used."""
    from studio.voice.transcribe import Heard

    session_id = open_class(studio)
    monkeypatch.setattr(
        "studio.voice.transcribe.WhisperCppClient.hear",
        lambda self, audio, language="zh", filename="said.webm": Heard("my dog ran away", "en"),
    )
    body, content_type = multipart("audio", "said.webm", b"pretend-audio")
    status, heard = call(studio, "POST", f"/api/session/{session_id}/heard", body, content_type)
    assert status == 200
    assert heard["text"] == "my dog ran away"


def test_a_recording_through_the_route_is_timed_in_the_log(studio, monkeypatch, capsys):
    """studio/voice/audio_in.py's line, reached through the classroom: without it a slow one says nothing."""
    from studio.voice.transcribe import Heard

    session_id = open_class(studio)
    monkeypatch.setattr("studio.voice.transcribe.WhisperCppClient.hear",
                        lambda self, audio, language="zh", filename="said.webm": Heard("my dog ran away", "en"))
    body, content_type = multipart("audio", "said.wav", b"RIFF-pretend-audio")
    call(studio, "POST", f"/api/session/{session_id}/heard", body, content_type)
    assert "hearing: 0 KB as sent" in capsys.readouterr().err


def test_a_recording_the_studio_cannot_unpack_is_answered_as_the_studios_failing(studio, monkeypatch):
    """400 unreadable_audio, not the 503 the page reads as "nothing was heard" (review)."""
    session_id = open_class(studio)
    monkeypatch.setenv("PATH", "")
    body, content_type = multipart("audio", "said.webm", b"\x1a\x45\xdf\xa3" + b"\x00" * 64)
    with pytest.raises(urllib.error.HTTPError) as caught:
        call(studio, "POST", f"/api/session/{session_id}/heard", body, content_type)
    assert caught.value.code == 400
    assert json.loads(caught.value.read())["code"] == "unreadable_audio"


def test_no_transcription_model_says_so_rather_than_failing_silently(studio, monkeypatch, capsys):
    from studio.core.errors import ModelUnavailable

    session_id = open_class(studio)

    def dead(self, audio, language="zh", filename="said.webm"):
        raise ModelUnavailable("whisper-server is not running")

    monkeypatch.setattr("studio.voice.transcribe.WhisperCppClient.hear", dead)
    body, content_type = multipart("audio", "said.webm", b"pretend-audio")
    with pytest.raises(urllib.error.HTTPError) as caught:
        call(studio, "POST", f"/api/session/{session_id}/heard", body, content_type)
    assert caught.value.code == 503
    # The studio's own log says why, not only that it failed.
    assert "hearing failed: whisper-server is not running" in capsys.readouterr().err


def test_the_board_is_served_by_the_studio_itself(studio):
    """One address for the teacher. The board had its own port and its own
    command, which is a thing to be told rather than a thing to be found."""
    status, body = call(studio, "GET", "/board")
    assert status == 200
    assert "组件监控" in body.decode("utf-8")


def test_the_studio_answers_the_board_its_readings(studio):
    """The board page polls /api/lights on whatever origin serves it."""
    status, reading = call(studio, "GET", "/api/lights")
    assert status == 200
    assert reading["profile"]
    assert [light["slot"] for light in reading["lights"]], "a board with no lights is a dead machine"


def test_the_prompt_page_can_read_every_instruction_and_change_none(studio):
    status, book = call(studio, "GET", "/api/prompts")
    assert status == 200
    assert {"feedback", "safety", "agent"} <= {group["id"] for group in book["groups"]}
    for verb in ("POST", "PATCH", "DELETE"):
        with pytest.raises(urllib.error.HTTPError) as refused:
            call(studio, verb, "/api/prompts", {"text": "changed"})
        assert refused.value.code == 404


def test_the_teacher_can_reach_the_board_without_being_told_a_port():
    """The entrance itself: a way in from the page, not a URL in someone's notes."""
    from pathlib import Path

    page = Path("studio/page/index.html").read_text(encoding="utf-8")
    assert 'id="portfolio-admin"' in page, "no management entrance in the course collection"
    assert "$('portfolio-admin').addEventListener('click', openAdmin)" in page
    assert 'id="admin-board"' in page, "no service details inside management"
    assert 'id="deployment-check"' in page
    assert 'id="deployment-options"' in page
    assert 'deployments.open' in page, 'management must open the integrated status view'



def test_the_page_cannot_be_put_into_another_language():
    """One language, and no way to leave it.

    A CN/EN switch used to sit in the bar, with an English table behind
    it. Teachers pressed it by accident and then could not read the studio well
    enough to put it back: a switch that can strand its user is worse than no
    switch, so the operator had both removed.

    This reads the built page rather than the parts, because the parts are what
    someone edits and the page is what a teacher is served. Each thing is named
    on its own: a sweep that passed over an empty set would pass for the wrong
    reason.
    """
    from pathlib import Path

    page = Path("studio/page/index.html").read_text(encoding="utf-8")
    assert 'id="btn-lang"' not in page, "the language switch is back in the bar"
    assert 'class="seg" id="lang"' not in page, "the older language segment is back"
    assert "Studio.strings.en" not in page, "an English table is back in the page"
    assert "i18n.set(" not in page, "something can still change the language"
    assert 'lang="zh"' in page, "the page no longer says which language it is in"


def test_the_studio_reads_as_chinese_before_a_word_of_script_has_run():
    """What a teacher sees first is not written by JavaScript.

    Splat once greeted in English over a Chinese studio because the language was
    set after the companion was initialised. There is no language to set now; the
    labels are written into the markup by the build, so the question is simply
    whether the markup carries them.
    """
    from pathlib import Path

    page = Path("studio/page/index.html").read_text(encoding="utf-8")
    markup = page[: page.index("<script>")]
    for word in ("画里画外", "聊聊你的画", "全部课程"):
        assert word in markup, f"{word} is not in the bytes the browser paints first"
    assert "Talk about it" not in markup, "an English label is painted"


def test_showcase_routes(studio):
    status, body = call(studio, 'GET', '/showcase/3d')
    assert status == 200 and b'type="importmap"' in body
    status, viewer = call(studio, 'GET', '/viewer/3d/classroom.html')
    assert status == 200 and b'data-mode="classroom"' in viewer
    status, ui = call(studio, 'GET', '/viewer/3d/classroom-ui.js')
    assert status == 200 and b'localizeClassroom' in ui
    status, manifest = call(studio, 'GET', '/showcase/3d/manifest.json')
    assert status == 200 and len(manifest['samples']) == 3
    status, script = call(studio, 'GET', '/showcase/3d/viewer.js')
    assert status == 200 and b'WebGLRenderer' in script
    status, figure = call(studio, 'GET', '/viewer/3d/figure.html')
    assert status == 200 and b'figure.js' in figure
    status, figure = call(studio, 'GET', '/viewer/3d/figure.js')
    assert status == 200 and b'figure-viewer-loaded' in figure
    for path in ['lineage.json', 'serve.py', 'originals/model.obj', 'assets/%2e%2e/serve.py']:
        with pytest.raises(urllib.error.HTTPError) as error:
            call(studio, 'GET', '/showcase/3d/' + path)
        assert error.value.code == 404


def test_deployment_routes_keep_current_on_invalid_input(studio):
    status, result = call(studio, 'GET', '/api/deployments')
    assert status == 200 and result['selected'] == 'current'
    assert [item['id'] for item in result['options']] == ['stepfun']  # the only one
    with pytest.raises(urllib.error.HTTPError) as error:
        call(studio, 'POST', '/api/deployments', {'deployment': '../../private'})
    assert error.value.code == 400
    assert call(studio, 'GET', '/api/deployments')[1]['selected'] == 'current'
    sid = call(studio, 'POST', '/api/session', CLASS)[1]['session_id']
    assert call(studio, 'GET', '/api/deployments?session_id='+sid)[1]['session']['deployment'] == 'current'


def test_the_classroom_serves_the_harness_page(studio):
    """Beyond Canvas is one system, so its own port answers for the diagram of
    the harness behind it. At first only the exhibit on 7090 did, and
    `7060/harness` returned the route table's 404 -- which reads as "broken",
    not as "somewhere else".
    """
    status, body = call(studio, "GET", "/harness/")
    assert status == 200
    assert b"<title>Harness</title>" in body


def test_the_bare_harness_path_redirects_to_the_slash(studio):
    """Everything the page loads is relative. From `/harness` the browser would
    resolve `harness.js` to `/harness.js` and get nothing, so the page would
    render its shell and stay empty -- a failure that looks like a bug in the
    page rather than a missing slash.
    """
    request = urllib.request.Request(studio + "/harness", method="GET")
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.build_opener(NoRedirect).open(request)
    assert caught.value.code == 302
    assert caught.value.headers["Location"] == "/harness/"


def test_the_harness_page_gets_every_file_it_asks_for(studio):
    """The page names its own dependencies: two stylesheets and a module in the
    HTML, two module imports inside that module, three JSON files fetched at
    boot. A missing one is a blank panel, not an error, so each is asked for.
    """
    for name in ("style.css", "harness.css", "harness.js", "harnessplay.mjs",
                 "harnessboard.mjs", "harness-strings.json", "harness-roster.json",
                 "harness-journeys.json"):
        status, body = call(studio, "GET", f"/harness/{name}")
        assert status == 200, f"{name} did not come back"
        assert body, f"{name} came back empty"


def test_the_harness_route_hands_out_nothing_else_in_that_folder(studio):
    """It serves out of the exhibit's page directory, which also holds the temple
    demo and its vendored 3D library. Only the Harness page's own files are the
    classroom's to serve.
    """
    for name in ("app.js", "index.html", "viewer.mjs", "../serve.py"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            call(studio, "GET", f"/harness/{name}")
        assert caught.value.code == 404, f"{name} was served"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stops urllib following the 302 so the redirect itself can be read."""

    def redirect_request(self, *args, **kwargs):
        return None


def test_the_route_count_in_the_docstring_is_the_real_one():
    """`serve.py` opens by saying how few routes it has, as the reason the
    standard library is enough. It said seven from the day it was written until
    it was corrected, by which point there were 38 -- nobody had lied, the sentence
    had simply stopped being re-read while routes were added under it.

    A number in prose has no way to go wrong loudly, so this is the thing that
    makes it go wrong loudly. It is the cheapest kind of check: the docstring is
    already in memory, and the count is already a `len`.
    """
    import re

    from studio import serve

    claimed = re.search(r"the routes are (\d+)", serve.__doc__)
    assert claimed, "the docstring no longer states a route count"
    assert int(claimed.group(1)) == len(serve.StudioHandler.ROUTES), (
        f"the docstring says {claimed.group(1)} routes; there are "
        f"{len(serve.StudioHandler.ROUTES)}")


def test_the_classroom_serves_the_temple_showpiece(studio):
    """The other half of "no need a dedicated port": the temple dashboard opens
    on 7060 like the Harness page does. The exhibit on 7090 still serves it from
    the same code, which is what keeps there being one copy.
    """
    status, body = call(studio, "GET", "/showpiece/")
    assert status == 200
    assert b"<title>" in body and b"app.js" in body


def test_the_showpiece_answers_a_kept_open_connection_in_order(studio):
    """The classroom speaks HTTP/1.1 and a browser sends its next request down the same connection,
    so a "you have it" (304) must carry no body, or the next answer would be read as part of it."""
    from http.client import HTTPConnection
    from urllib.parse import urlsplit

    address = urlsplit(studio)
    conn = HTTPConnection(address.hostname, address.port)
    asks = {"Accept-Encoding": "gzip"}
    conn.request("GET", "/showpiece/vendor/three.module.js", headers=asks)
    first = conn.getresponse()
    packed, tag = first.read(), first.getheader("ETag")
    assert first.status == 200 and first.getheader("Content-Encoding") == "gzip" and tag
    conn.request("GET", "/showpiece/vendor/three.module.js", headers={**asks, "If-None-Match": tag})
    again = conn.getresponse()
    assert again.status == 304 and again.read() == b""
    conn.request("GET", "/showpiece/vendor/three.module.js", headers=asks)
    third = conn.getresponse()
    assert third.status == 200 and third.read() == packed
    conn.close()


def test_the_classroom_serves_the_recorded_rebuild_player(studio):
    status, page = call(studio, "GET", "/showpiece/rebuild.html")
    assert status == 200 and b"rebuild.mjs" in page
    status, record = call(studio, "GET", "/showpiece/rebuild-record.json")
    assert status == 200 and record["measured"]["adopted"] is True
    assert len(record["steps"]) == 145
    status, image = call(studio, "GET", "/showpiece/rebuild-step-126.jpg")
    assert status == 200 and image.startswith(b"\xff\xd8\xff")
    status, model = call(studio, "GET", "/showpiece/rebuild-hall.glb")
    assert status == 200 and model[:4] == b"glTF"
    status, hall = call(studio, "GET", "/showpiece/rebuild-hall.json")
    assert status == 200 and hall["rounds"]["step-126"]["shake"]["samples"] > 1
    status, path = call(studio, "GET", "/showpiece/rebuild-shake-step-126.gz")
    assert status == 200 and path[:2] == b"\x1f\x8b"
    status, model = call(studio, "GET", "/showpiece/rebuild-brackets.glb")
    assert status == 200 and model[:4] == b"glTF"
    status, module = call(studio, "GET", "/showpiece/rebuild-hall.mjs")
    assert status == 200 and b"GLTFLoader" in module


def test_the_classroom_serves_the_designs_beside_the_rebuilds(studio):
    status, listed = call(studio, "GET", "/showpiece/rebuild-designs.json")
    assert status == 200 and listed["designs"]
    for design in listed["designs"]:
        status, record = call(studio, "GET", f"/showpiece/rebuild-design{design['n']}-record.json")
        assert status == 200 and record["design"] is True
        status, model = call(studio, "GET", f"/showpiece/rebuild-design{design['n']}-hall.glb")
        assert status == 200 and model[:4] == b"glTF"


def test_the_bare_showpiece_path_redirects_to_the_slash(studio):
    """Its scripts, its 3D library and now its API calls are all relative, so the
    page only works from `/showpiece/`. Without the slash every one of them would
    resolve a level too high.
    """
    request = urllib.request.Request(studio + "/showpiece", method="GET")
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.build_opener(NoRedirect).open(request)
    assert caught.value.code == 302
    assert caught.value.headers["Location"] == "/showpiece/"


def test_the_showpiece_api_answers_under_its_own_prefix(studio):
    """The dashboard's URLs used to be absolute and are relative now,
    so the same page works at `/` on the exhibit and under `/showpiece/` here.
    These are the paths it actually asks for from the second of those.
    """
    status, payload = call(studio, "GET", "/showpiece/api/runs")
    assert status == 200 and isinstance(payload.get("runs"), list)

    status, payload = call(studio, "GET", "/showpiece/api/stats")
    assert status == 200 and "cpu_count" in payload


def test_an_ordinary_class_never_builds_the_temple(studio):
    """The whole reason the driver is lazy. A teacher opening a class must not
    pay for a model client, a key check or a 47 MB GLB export of a building they
    are not going to look at. Asking for health is an ordinary class's traffic;
    nothing of the showpiece should exist afterwards.
    """
    call(studio, "GET", "/api/health")
    holder = _server_of(studio).showpiece
    assert holder._driver is None, "the temple's driver was built by an ordinary request"


def test_the_showpiece_page_does_not_ask_for_the_site_root(studio):
    """A guard on the page rather than the server. If any of its URLs goes back
    to absolute, the page keeps working on 7090 and silently breaks here -- it
    would ask the classroom for /api/runs and get the classroom's 404. That is
    the failure this whole mount exists to avoid, and it is invisible from the
    exhibit, so it is checked from the page's own text.
    """
    from studio.showpiece.routes import PAGE

    for name in ("app.js", "screen.mjs"):
        text = (PAGE / name).read_text(encoding="utf-8")
        for absolute in ('"/api/', "`/api/", '"/strings.json"'):
            assert absolute not in text, f"{name} asks for {absolute}, which only works at the site root"


def _server_of(base):
    """The live StudioServer behind a fixture's base URL."""
    import gc

    from studio.serve import StudioServer

    port = int(base.rsplit(":", 1)[1])
    for obj in gc.get_objects():
        if isinstance(obj, StudioServer) and obj.server_address[1] == port:
            return obj
    raise AssertionError(f"no server on {port}")


# The page on a slow link ---------------------------------------------------
#
# The classroom is reached over a public address, and the page is one file of
# close to a megabyte. What can only go wrong out here: sending it compressed to
# a browser that cannot unpack it, sending it again to one that already has it,
# and keeping a browser on yesterday's page after a rebuild.

def fetch(address, headers=None, path="/"):
    """One GET, with exactly the headers the test names."""
    import http.client

    connection = http.client.HTTPConnection(address, timeout=20)
    try:
        connection.request("GET", path, headers=headers or {})
        reply = connection.getresponse()
        return reply.status, reply.headers, reply.read()
    finally:
        connection.close()


@pytest.fixture
def served_page(tmp_path):
    """A server whose page file the test can rewrite, to watch the tag follow it."""
    client = Scripted([])
    classroom = Classroom(
        tmp_path / "ledger.jsonl", clients={"vlm.studio": client, "vlm.director": client}
    )
    page = tmp_path / "index.html"
    page.write_text("<title>Beyond Canvas</title>" + "<p>一间教室</p>" * 3000, encoding="utf-8")
    entrance = tmp_path / "assets" / "entrance"
    entrance.mkdir(parents=True)
    # Not a real JPEG, but bytes that gzip would happily shrink -- which is how
    # the test can tell that a photograph is deliberately sent uncompressed.
    (entrance / "colour-painting.jpg").write_bytes(b"\xff\xd8\xff" + b"a picture" * 4000)
    server = make_server(classroom, "127.0.0.1", 0, page)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"127.0.0.1:{server.server_address[1]}", page
    server.shutdown()
    server.server_close()
    classroom.close()


def test_the_page_is_compressed_for_a_browser_that_can_unpack_it(served_page):
    import gzip

    address, page = served_page
    status, headers, body = fetch(address, {"Accept-Encoding": "gzip"})
    assert status == 200 and headers.get("Content-Encoding") == "gzip"
    assert headers.get("Vary") == "Accept-Encoding", "a cache could hand this to a browser that cannot read it"
    assert gzip.decompress(body).decode("utf-8") == page.read_text(encoding="utf-8")
    assert len(body) < len(page.read_bytes()) / 4, f"{len(body)} bytes saved almost nothing"


def test_a_browser_that_cannot_unpack_gzip_still_gets_the_page(served_page):
    address, page = served_page
    status, headers, body = fetch(address)
    assert status == 200 and headers.get("Content-Encoding") is None
    assert body == page.read_bytes()


def test_a_browser_that_already_has_the_page_is_not_sent_it_again(served_page):
    address, _ = served_page
    status, headers, body = fetch(address)
    tag = headers.get("ETag")
    assert status == 200 and tag and headers.get("Cache-Control") == "no-cache"
    status, headers, again = fetch(address, {"If-None-Match": tag})
    assert status == 304 and again == b""
    assert headers.get("ETag") == tag


def test_the_compressed_page_and_the_plain_one_are_told_apart(served_page):
    """One tag for both let a browser holding the gzipped page be told 304 when it asked without gzip, and keep
    bytes it could not read (code review). Each is kept under its own tag now."""
    address, page = served_page
    _, headers, _ = fetch(address, {"Accept-Encoding": "gzip"})
    packed = headers.get("ETag")
    _, headers, _ = fetch(address)
    plain = headers.get("ETag")
    assert packed and plain and packed != plain
    status, headers, body = fetch(address, {"If-None-Match": packed})
    assert status == 200 and headers.get("Content-Encoding") is None and body == page.read_bytes()
    status, _, body = fetch(address, {"Accept-Encoding": "gzip", "If-None-Match": packed})
    assert status == 304 and body == b""


def test_a_rebuilt_page_is_sent_rather_than_the_one_the_browser_holds(served_page):
    """`no-cache` means ask every time, so a class never opens yesterday's page."""
    address, page = served_page
    _, headers, _ = fetch(address)
    stale = headers.get("ETag")
    assert stale, "the page went out with no tag for a browser to quote back"
    page.write_text("<title>Beyond Canvas</title><p>今天的课</p>", encoding="utf-8")
    status, headers, body = fetch(address, {"If-None-Match": stale})
    assert status == 200, "the browser was left holding the page from before the rebuild"
    assert headers.get("ETag") != stale
    assert "今天的课".encode() in body


def test_an_entrance_photograph_is_a_file_of_its_own_now(served_page):
    """They used to be written into the page as base64: 437 KB, 47% of it, and
    base64 of a JPEG compresses to nothing. Now the browser can keep them."""
    address, page = served_page
    status, headers, body = fetch(address, path="/assets/entrance/colour-painting.jpg")
    assert status == 200 and headers.get("Content-Type") == "image/jpeg"
    assert body == (page.parent / "assets/entrance/colour-painting.jpg").read_bytes()
    assert headers.get("ETag") and headers.get("Cache-Control") == "no-cache"


def test_a_photograph_already_in_the_browser_is_not_sent_again(served_page):
    address, _ = served_page
    _, headers, _ = fetch(address, path="/assets/entrance/colour-painting.jpg")
    tag = headers.get("ETag")
    assert tag, "the photograph went out with no tag for a browser to quote back"
    status, _, body = fetch(address, {"If-None-Match": tag}, path="/assets/entrance/colour-painting.jpg")
    assert status == 304 and body == b""


def test_a_photograph_is_sent_as_it_is_rather_than_gzipped(served_page):
    """A JPEG is already compressed; packing it again spends time for nothing."""
    address, page = served_page
    status, headers, body = fetch(address, {"Accept-Encoding": "gzip"},
                                  path="/assets/entrance/colour-painting.jpg")
    assert status == 200 and headers.get("Content-Encoding") is None
    assert body == (page.parent / "assets/entrance/colour-painting.jpg").read_bytes()


def test_only_a_photograph_in_that_folder_can_be_asked_for(served_page):
    """The route's pattern is the guard: a name it allows holds no slash."""
    address, _ = served_page
    for path in ("/assets/entrance/sketch-study.jpg", "/assets/entrance/colour-painting.png",
                 "/assets/entrance/../../../etc/passwd"):
        status, _, _ = fetch(address, path=path)
        assert status == 404, f"{path} was served"


def test_a_deleted_class_is_named_in_the_log_with_the_browser_that_asked(tmp_path, capsys):
    """Two new classes were once deleted seconds after they were made, and nothing said by what."""
    from studio.classroom.portfolio import Portfolio

    client = Scripted([ALLOW])
    classroom = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": client, "vlm.director": client},
                          portfolio=Portfolio(tmp_path / "courses.sqlite3"))
    page = tmp_path / "index.html"
    page.write_text("<title>Beyond Canvas</title>", encoding="utf-8")
    server = make_server(classroom, "127.0.0.1", 0, page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        course_id = open_class(base, {**CLASS, "title": "Storybook test"})
        request = urllib.request.Request(base + f"/api/courses/{course_id}", method="DELETE",
                                         headers={"User-Agent": "Mozilla/5.0 Chrome/140"})
        with urllib.request.urlopen(request, timeout=20) as reply:
            assert reply.status == 204
        line = next(l for l in capsys.readouterr().err.splitlines() if "class deleted" in l)
        assert course_id in line and '"Storybook test"' in line and "0 drawing(s)" in line and "Chrome/140" in line
    finally:
        server.shutdown()
        server.server_close()
        classroom.close()
