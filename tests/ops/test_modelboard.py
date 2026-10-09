"""The board that says which model servers are actually up.

It is the answer to "is it loaded?" that does not require trusting a document.
Everything it shows is measured when the page asks, so the tests here are about
never letting it claim more than it measured.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from studio.ops.modelboard import (
    BLOCKED_PORTS,
    REQUESTED_PORT,
    Light,
    page_html,
    port_of,
    read_board,
    usable_port,
)


class _Probe:
    """Stands in for the network: answers from a table, records what was asked."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def __call__(self, url, timeout=0.0):
        self.asked.append(url)
        return self.answers.get(url)


@pytest.mark.parametrize("slot", ["vlm.sketch", "vlm.voice_lab"])
def test_a_port_that_answers_is_lit(slot):
    probe = _Probe({"http://127.0.0.1:7100": "step3-vl-10b"})
    lights = read_board("local", probe=probe)
    studio = next(light for light in lights if light.slot == slot)
    assert studio.up is True
    assert studio.serving == "step3-vl-10b"


@pytest.mark.parametrize("slot", ["vlm.sketch", "vlm.voice_lab"])
def test_a_port_that_does_not_answer_is_dark_and_says_so(slot):
    lights = read_board("local", probe=_Probe({}))
    studio = next(light for light in lights if light.slot == slot)
    assert studio.up is False
    assert studio.note, "a dark light must say why it is dark"


@pytest.mark.parametrize("slot", ["vlm.studio", "vlm.director"])
def test_a_hosted_slot_is_never_probed(slot):
    """The director runs on someone else's machine. Polling localhost for it
    would report it down forever, which is worse than saying it is elsewhere."""
    probe = _Probe({})
    lights = read_board("local", probe=probe)
    director = next(light for light in lights if light.slot == slot)
    assert director.url == ""
    assert director.hosted is True
    assert director.up is None, "hosted is neither up nor down from here"
    assert director.note, "and it must say why it is neither"
    assert all(url.startswith("http://127.0.0.1:") for url in probe.asked)
    assert not any("7110" in url for url in probe.asked), "the hosted slot was polled"


def test_every_slot_in_the_profile_gets_a_light():
    """However many slots the profile has, that is how many lights appear.

    This counted to eleven until video.scene and rig.figure
    were deleted and it failed for being right about the old roster. The claim
    worth keeping is not the number, it is that the board shows the profile it
    was given and does not quietly drop a slot.

    Later the same day it failed again, and again for being right about
    something that had changed underneath it: it subtracted EVERY name in
    EXTRA_PORTS, which assumed no extra could ever also be a profile slot.
    `speech.in` became one when the spark profile finally gained the listening
    model. So subtract only the extras this profile does not itself define —
    which is the same set the board now declines to add twice.
    """
    from studio.ops.modelboard import EXTRA_PORTS
    from studio.core.slots import load_profile

    expected = set(load_profile("spark"))
    lights = read_board("spark", probe=_Probe({}))
    only_extra = {e[0] for e in EXTRA_PORTS} - expected
    shown = {light.slot for light in lights} - only_extra
    assert shown == expected, f"board shows {sorted(shown)}, profile has {sorted(expected)}"
    assert len(lights) == len({light.slot for light in lights}), "a slot is lit twice"
    assert {"vlm.studio", "video.animation", "tts.export"} <= shown


def test_the_ports_outside_the_profiles_are_on_the_board_too():
    """Whisper and the page are real ports this product uses, and neither is a
    model slot. A ports list that omits them is not a ports list."""
    slots = {light.slot for light in read_board("local", probe=_Probe({}))}
    assert "speech.in" in slots
    assert "studio.page" in slots


def test_the_board_reports_a_port_used_twice():
    """The detector, not the bug it was written for.

    `studio/serve.py` and the local studio model both used to default to 8080,
    so whichever started second could not bind. The port convention
    in tests/server/test_ports.py stops that arrangement being written down again; this
    is what shows it on the board if two servers collide on the day anyway, which
    a config file cannot know about.
    """
    from studio.ops.modelboard import _mark_clashes

    sharing = [
        Light(slot="vlm.studio", model="a", url="http://127.0.0.1:7100"),
        Light(slot="studio.page", model="b", url="http://127.0.0.1:7100"),
        Light(slot="speech.in", model="c", url="http://127.0.0.1:7130"),
    ]
    _mark_clashes(sharing)
    assert sharing[0].clash == ["studio.page"]
    assert sharing[1].clash == ["vlm.studio"]
    assert not sharing[2].clash, "a port used once is not a collision"


def test_the_shipped_profiles_have_no_collision_left():
    """The state the convention exists to hold."""
    lights = read_board("local", probe=_Probe({}))
    assert not [light.slot for light in lights if light.clash]


def test_request_aliases_share_a_model_but_still_report_a_different_server():
    from studio.ops.modelboard import _mark_clashes
    lights = [Light(slot=slot, model="step3-vl-10b", url="http://127.0.0.1:7100")
              for slot in ("vlm.studio", "vlm.sketch")]
    _mark_clashes(lights)
    assert all(not light.clash for light in lights)
    lights.append(Light(slot="studio.page", model="studio/serve.py", url=lights[0].url))
    _mark_clashes(lights)
    assert lights[0].clash == lights[1].clash == ["studio.page"]
    assert lights[2].clash == ["vlm.studio", "vlm.sketch"]


def test_port_of_reads_the_port_out_of_a_url():
    assert port_of("http://127.0.0.1:7220") == 7220
    assert port_of("") is None


# --- The port the browser will actually open ---------------------------------

def test_six_thousand_is_known_to_be_refused_by_browsers():
    """Measured: curl fetches it, Chrome refuses to navigate. It is
    X11's port and sits on every browser's blocked list."""
    assert REQUESTED_PORT == 6000
    assert 6000 in BLOCKED_PORTS


def test_the_default_port_is_the_nearest_one_a_browser_will_open():
    assert usable_port(6000) == 6001
    assert usable_port(6001) == 6001


def test_a_port_the_browser_blocks_is_never_returned():
    for blocked in sorted(BLOCKED_PORTS):
        assert usable_port(blocked) not in BLOCKED_PORTS


# --- The page itself ---------------------------------------------------------

def test_the_page_reaches_no_network(monkeypatch):
    """The product's own rule: pull the cable and everything still works. A
    status page for an offline box that needs a font server is a joke."""
    html = page_html("local", 6001)
    for forbidden in ("http://fonts", "https://", "cdn", "//fonts.googleapis"):
        assert forbidden not in html, forbidden


def test_the_page_names_the_port_it_is_on_and_the_one_that_was_asked_for():
    html = page_html("local", 6001)
    assert "6001" in html
    assert "6000" in html


def test_the_light_payload_is_json_a_page_can_read():
    lights = read_board("local", probe=_Probe({}))
    payload = json.loads(json.dumps([light.as_dict() for light in lights]))
    assert payload
    assert {"slot", "model", "up", "hosted", "port"} <= set(payload[0])


def test_an_unknown_profile_is_refused_rather_than_served_empty():
    with pytest.raises(FileNotFoundError):
        read_board("nosuchprofile", probe=_Probe({}))


# --- A port already in use ----------------------------------------------------
# Reported as "command crashed". Running the board while a board was
# already up printed twenty lines of Python traceback ending in OSError errno 48.
# The situation is ordinary and the remedy is one sentence, so a traceback is the
# wrong answer twice: it looks like a defect, and it buries what to do.

def test_a_taken_port_is_explained_rather_than_thrown(capsys):
    import socket

    from studio.ops.modelboard import serve

    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    taken = holder.getsockname()[1]
    try:
        serve("local", taken)  # must return, not raise
    finally:
        holder.close()
    said = capsys.readouterr().out
    assert str(taken) in said, "the message must name the port"
    assert "--port" in said, "and must say how to run a second one"


def test_a_taken_port_does_not_leave_the_caller_thinking_it_started(capsys):
    """It returns, so main() exits cleanly, and it says nothing about serving."""
    import socket

    from studio.ops.modelboard import serve

    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    taken = holder.getsockname()[1]
    try:
        serve("local", taken)
    finally:
        holder.close()
    said = capsys.readouterr().out
    assert "Model board on" not in said


# --- Where the model lives, and what it is costing ----------------------------
# Asked for: local or online, and if local the path, the disk it
# occupies and the memory it holds. A slot name alone does not tell you whether
# a child's drawing left the building.

def test_a_local_slot_says_it_is_local_and_a_hosted_one_says_online():
    lights = read_board("local", probe=_Probe({}))
    studio = next(light for light in lights if light.slot == "vlm.studio")
    director = next(light for light in lights if light.slot == "vlm.director")
    sketch = next(light for light in lights if light.slot == "vlm.sketch")
    voice = next(light for light in lights if light.slot == "vlm.voice_lab")
    assert sketch.where == voice.where == "local"
    assert studio.where == director.where == "online"


@pytest.mark.parametrize("slot", ["vlm.sketch", "vlm.voice_lab"])
def test_a_running_local_model_reports_its_path_and_disk(monkeypatch, slot):
    """The path comes from the command line of whatever holds the port, so it is
    the file actually loaded rather than the one a config hoped for."""
    import studio.ops.modelusage as usage

    monkeypatch.setattr(usage, "_serving_argv", lambda port: (
        ["llama-server", "-m", "/models/weights.gguf", "--mmproj", "/models/proj.gguf"], 4321))
    monkeypatch.setattr(usage, "_bytes_on_disk", lambda path: 2 * 1024**3)
    monkeypatch.setattr(usage, "_resident_bytes", lambda pid: 5 * 1024**3)

    lights = read_board("local", probe=_Probe({"http://127.0.0.1:7100": "step3-vl"}))
    studio = next(light for light in lights if light.slot == slot)
    assert studio.paths == ["/models/weights.gguf", "/models/proj.gguf"]
    assert studio.disk_gb == 4.0, "both the weights and the projector count"
    assert studio.ram_gb == 5.0


@pytest.mark.parametrize("slot", ["vlm.studio", "vlm.director"])
def test_a_hosted_slot_has_no_path_disk_or_memory(slot):
    """Asking the size of a model on someone else's machine is meaningless."""
    lights = read_board("local", probe=_Probe({}))
    director = next(light for light in lights if light.slot == slot)
    assert director.paths == []
    assert director.disk_gb is None
    assert director.ram_gb is None


@pytest.mark.parametrize("slot", ["vlm.sketch", "vlm.voice_lab"])
def test_a_local_slot_that_is_down_reports_no_usage(slot):
    """Nothing is loaded, so nothing is occupied. Zero would be a claim."""
    lights = read_board("local", probe=_Probe({}))
    studio = next(light for light in lights if light.slot == slot)
    assert studio.up is False
    assert studio.ram_gb is None


def test_the_payload_carries_the_new_fields():
    lights = read_board("local", probe=_Probe({}))
    payload = lights[0].as_dict()
    assert {"where", "paths", "disk_gb", "ram_gb"} <= set(payload)


class _Answers(BaseHTTPRequestHandler):
    """A server that publishes health where the studio page publishes it."""

    ROUTE = "/api/health"

    def do_GET(self):  # noqa: N802 - the name http.server requires
        body = b'{"ok": true}'
        code = 200 if self.path == self.ROUTE else 404
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _served(handler):
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_probe_finds_a_page_that_publishes_health_where_the_page_contract_says():
    """The board called the running studio page down for a day.

    It asked /v1/models and /health, which is where a llama.cpp server answers.
    The page answers at /api/health, settled by the page contract, so the one
    service a teacher actually opens was the one service the board could not
    see. A status board that reports a running thing as down teaches people to
    ignore it, which costs more than having no board.
    """
    from studio.ops.modelusage import probe

    server, url = _served(_Answers)
    try:
        assert probe(url, timeout=2.0) is not None
    finally:
        server.shutdown()
        server.server_close()


def test_probe_still_reads_the_model_name_from_a_llama_style_server():
    """The path that already worked, held down while the other one is added."""
    from studio.ops.modelusage import probe

    class Models(_Answers):
        ROUTE = "/v1/models"

        def do_GET(self):  # noqa: N802 - the name http.server requires
            if self.path != self.ROUTE:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b'{"data": [{"id": "/models/step3-vl-10b.gguf"}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server, url = _served(Models)
    try:
        assert probe(url, timeout=2.0) == "step3-vl-10b.gguf"
    finally:
        server.shutdown()
        server.server_close()


def test_nothing_listening_is_still_nothing():
    """The absence has to survive the new fallback, or every port reads as up."""
    from studio.ops.modelusage import probe

    server, url = _served(_Answers)
    server.shutdown()
    server.server_close()
    assert probe(url, timeout=1.0) is None


def _free_port():
    """A port nothing holds right now.

    These two tests bound 7040 and 7050 by hand until another
    window started a studio on 7040 and the suite went red for a reason that had
    nothing to do with the board.
    """
    import socket

    with socket.socket() as finding:
        finding.bind(("127.0.0.1", 0))
        return finding.getsockname()[1]


def test_the_board_answers_a_second_reader_while_the_first_is_still_measuring():
    """One slow measurement must not starve the page polling every 5 seconds.

    Found live, minutes after the probe learned to see the studio
    page: one more light meant one more lsof and ps per reading, the reading
    grew past the poll interval, and a plain HTTPServer serves one request at a
    time. The board stopped answering anything at all — connections accepted,
    nothing returned, the static page included — which reads as a hung machine
    rather than a slow one.

    The measuring lives at /api/lights. A test against / proves nothing: that
    path reads a file and returns, however stuck the rest of the board is.
    """
    import time
    import urllib.request

    from studio.ops import modelboard

    slow = 0.8
    original = modelboard.read_board
    modelboard.read_board = lambda *a, **k: time.sleep(slow) or []
    try:
        port = _free_port()
        threading.Thread(target=modelboard.serve, args=("local", port), daemon=True).start()
        time.sleep(0.3)

        answered = []

        def read():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/lights", timeout=20) as reply:
                answered.append(reply.status)

        started = time.monotonic()
        readers = [threading.Thread(target=read) for _ in range(2)]
        for reader in readers:
            reader.start()
        for reader in readers:
            reader.join(timeout=20)
        elapsed = time.monotonic() - started

        assert answered == [200, 200], f"only {len(answered)} of 2 readers were answered"
        assert elapsed < slow * 1.8, (
            f"two readers took {elapsed:.1f}s for a {slow}s reading, so the second "
            "waited for the first")
    finally:
        modelboard.read_board = original


def test_a_client_that_connects_and_says_nothing_cannot_close_the_board():
    """What actually took the board down.

    A browser opens speculative connections and sends nothing on them. A plain
    HTTPServer reads the request line on its only thread, with no socket
    timeout, so it waits there forever: the listen queue fills, new connections
    are never accepted, and every reader — including the static page — times out
    at connect. The process stays alive and holds the port, which is why it
    looks like a hung machine rather than a stuck request.
    """
    import socket
    import time
    import urllib.request

    from studio.ops import modelboard

    original = modelboard.read_board
    modelboard.read_board = lambda *a, **k: []
    silent = socket.socket()
    try:
        port = _free_port()
        threading.Thread(target=modelboard.serve, args=("local", port), daemon=True).start()
        time.sleep(0.3)

        silent.connect(("127.0.0.1", port))          # connects, then says nothing
        time.sleep(0.2)

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/lights", timeout=5) as reply:
            assert reply.status == 200, "the board stopped answering everyone else"
    finally:
        silent.close()
        modelboard.read_board = original


def test_dashboard_exposes_real_status_and_filters():
    html = page_html("local", 7020)
    assert "画室的功能伙伴" in html
    assert "color-scheme:light" in html
    assert 'data-filter="reserved"' in html
    assert "未统计调用量" in html
    assert "AbortSignal.timeout" in html


def test_usage_distinguishes_retained_config_from_classroom_route():
    lights = {light.slot: light for light in read_board("local", probe=_Probe({}))}
    assert lights["mesh.fast"].usage == "仅保留配置"
    assert lights["mesh.portrait"].usage == "配置路径"
    assert "Pixal3D" in lights["mesh.portrait"].purpose
    assert lights["vlm.voice_lab"].usage == "独立实验"
    assert all(light.purpose for light in lights.values())
