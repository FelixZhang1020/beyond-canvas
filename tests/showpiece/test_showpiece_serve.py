"""The exhibit's routes: start a run, stream its events, serve its files, refuse escapes."""
import gzip
import json
import struct
import threading
import urllib.error
import urllib.request
from http.client import HTTPConnection

import pytest
from conftest import FakeClient

from studio.showpiece import serve as exhibit
from studio.showpiece.driver import Driver


@pytest.fixture
def server(tmp_path, monkeypatch):
    # A live run is refused where there is no Blender; these tests drive a fake agent, so the
    # machine running them need not have one.
    monkeypatch.setattr("studio.showpiece.blender_bin.find_blender", lambda: tmp_path / "blender")
    client = FakeClient([json.dumps({"think": "t", "final": "nothing to do"})] * 3)
    driver = Driver(client, None, tmp_path / "runs", cap=2)
    httpd = exhibit.make_server(0, driver, exhibit.PAGE)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()


def get(httpd, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_port}{path}") as r:
        return r.status, r.read()


def start_run(httpd, request):
    conn = HTTPConnection("127.0.0.1", httpd.server_port)
    conn.request("POST", "/api/runs", body=json.dumps({"request": request}), headers={"Content-Type": "application/json"})
    return json.loads(conn.getresponse().read())["id"]


def test_the_page_and_a_run_and_its_stream(server):
    status, body = get(server, "/")
    assert status == 200 and b"<title>" in body
    run_id = start_run(server, "hello")
    status, stream = get(server, f"/api/runs/{run_id}/events")
    assert status == 200 and b"event: done" in stream and b'"final"' in stream
    status, listing = get(server, "/api/runs")
    assert json.loads(listing)["runs"][0]["id"] == run_id
    status, stats = get(server, "/api/stats")
    stats = json.loads(stats)
    assert status == 200 and "memory_total_gb" in stats and "cpu_percent" in stats and "host" in stats
    listed = json.loads(listing)["runs"][0]
    assert listed["recorded"] is False and listed["showpiece"] is None, "a run with no plan file yet"


def test_without_blender_a_live_run_is_refused_and_the_demos_still_list(server, monkeypatch):
    """The hosted Spark plays recorded demos only; live runs are made on the Mac."""
    monkeypatch.setattr("studio.showpiece.blender_bin.find_blender", lambda: None)
    conn = HTTPConnection("127.0.0.1", server.server_port)
    conn.request("POST", "/api/runs", body=json.dumps({"request": "hello"}), headers={"Content-Type": "application/json"})
    reply = conn.getresponse()
    assert reply.status == 503 and json.loads(reply.read())["code"] == "no_blender"
    status, listing = get(server, "/api/runs")
    assert status == 200 and json.loads(listing)["runs"] == []


def test_files_under_the_run_folder_only(server):
    run_id = start_run(server, "x")
    get(server, f"/api/runs/{run_id}/events")
    status, body = get(server, f"/api/runs/{run_id}/files/events.jsonl")
    assert status == 200 and b'"final"' in body
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(server, f"/api/runs/{run_id}/files/../../request.json")
    assert caught.value.code == 404


def test_a_run_id_cannot_walk_out_of_the_runs_folder(server, tmp_path):
    (tmp_path / "secret.txt").write_text("not for the page")
    for path in ("/api/runs/../files/secret.txt", "/api/runs/../events", "/api/runs/nowhere/events"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            get(server, path)
        assert caught.value.code == 404, path


def test_cross_origin_answers_go_to_this_machine_only(server):
    def allowed(origin):
        conn = HTTPConnection("127.0.0.1", server.server_port)
        conn.request("GET", "/api/stats", headers={"Origin": origin})
        return conn.getresponse().getheader("Access-Control-Allow-Origin")
    assert allowed("http://127.0.0.1:7060") == "http://127.0.0.1:7060"
    assert allowed("http://localhost:7060") == "http://localhost:7060"
    assert allowed("https://elsewhere.example") is None


@pytest.mark.parametrize("origin", ["https://elsewhere.example", "null"])
def test_a_page_from_elsewhere_cannot_start_a_run(server, origin):
    """A plain text/plain POST needs no cross-origin answer to arrive, so it is refused before it is read
    (code review); the studio page on this machine and a script with no Origin still start one."""
    conn = HTTPConnection("127.0.0.1", server.server_port)
    conn.request("POST", "/api/runs", body=json.dumps({"request": "hello"}),
                 headers={"Content-Type": "text/plain", "Origin": origin})
    reply = conn.getresponse()
    assert reply.status == 403
    assert json.loads(get(server, "/api/runs")[1])["runs"] == [], "nothing was started"
    conn = HTTPConnection("127.0.0.1", server.server_port)
    conn.request("POST", "/api/runs", body=json.dumps({"request": "hello"}),
                 headers={"Content-Type": "application/json", "Origin": "http://localhost:7060"})
    assert conn.getresponse().status == 201, "the studio page on this machine"
    assert start_run(server, "hello"), "a script, with no Origin"


def test_the_stream_beats_while_the_model_thinks(tmp_path):
    release = threading.Event()

    class Slow:
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            release.wait(10)
            return FakeClient([json.dumps({"think": "t", "final": "done"})]).chat(prompt, images, system=system, max_tokens=max_tokens)

    httpd = exhibit.make_server(0, Driver(Slow(), None, tmp_path / "runs", cap=2), exhibit.PAGE)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        run_id = start_run(httpd, "wait for it")
        conn = HTTPConnection("127.0.0.1", httpd.server_port, timeout=10)
        conn.request("GET", f"/api/runs/{run_id}/events")
        response = conn.getresponse()
        lines = []
        while len(lines) < 4:
            lines.append(response.readline().decode())
        assert any(line.startswith("event: busy") for line in lines), lines
        data = json.loads(next(line for line in lines if line.startswith("data:"))[5:])
        assert data["phase"] == "thinking" and "seconds" in data
        release.set()
        rest = response.read().decode()
        assert "event: done" in rest and '"final"' in rest
    finally:
        release.set()
        httpd.shutdown()


def test_the_3d_library_and_the_models_are_served_from_their_folders(server):
    status, body = get(server, "/vendor/three.module.js")
    assert status == 200 and b"three" in body[:400].lower()
    status, body = get(server, "/vendor/loaders/GLTFLoader.js")
    assert status == 200
    for path in ("/vendor/../serve.py", "/vendor/nope.js", "/api/models/nothing.glb"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            get(server, path)
        assert caught.value.code == 404, path
    start_run(server, "with a model field")
    status, listing = get(server, "/api/runs")
    assert "model" in json.loads(listing)["runs"][0]


def test_the_gpu_line_from_nvidia_smi_is_read_as_the_spark_really_prints_it():
    """The DGX Spark shares one pool of memory, so nvidia-smi has no separate GPU memory to report.

    Measured on the Spark: `memory.used,memory.total,utilization.gpu` answers
    "[N/A], [N/A], 0", and 96 in place of that 0 while it works. Until then this test asserted an
    invented line with real megabytes in it, which is why nobody noticed the console threw away a
    busy figure it had in its hand and told the teacher the GPU was unavailable.
    """
    assert exhibit.gpu_stats("[N/A], [N/A], 96") == {"used_gb": None, "total_gb": None, "util_percent": 96.0}
    assert exhibit.gpu_stats("12288, 131072, 37\n") == {"used_gb": 12.0, "total_gb": 128.0, "util_percent": 37.0}
    assert exhibit.gpu_stats("512, 8192, [N/A]") == {"used_gb": 0.5, "total_gb": 8.0, "util_percent": None}
    assert exhibit.gpu_stats("[N/A], [N/A], [N/A]") is None      # nothing usable is not a reading
    assert exhibit.gpu_stats("") is None and exhibit.gpu_stats("garbage") is None


def test_a_run_folder_without_its_events_is_not_listed(server):
    runs = server.driver.runs_root
    for name in ("recorded-tour", "recorded-tour.part"):
        (runs / name).mkdir(parents=True)
        (runs / name / "request.json").write_text(json.dumps({"request": "tour", "agent": "recorded"}))
    _, listing = get(server, "/api/runs")
    assert [r["id"] for r in json.loads(listing)["runs"]] == [], "a recording still being made is not a run yet"
    (runs / "recorded-tour" / "events.jsonl").write_text(json.dumps({"step": 1, "kind": "final", "text": "done"}) + "\n")
    _, listing = get(server, "/api/runs")
    assert [r["id"] for r in json.loads(listing)["runs"]] == ["recorded-tour"]


def test_the_harness_view_and_its_files_are_served(server):
    """The second page of the exhibit: the harness view, fed by its own data files."""
    def fetch(path):
        try:
            return get(server, path)
        except urllib.error.HTTPError as e:
            return e.code, b""
    status, body = fetch("/harness")
    assert status == 200 and b"harness.js" in body
    for name in ("harness.js", "harness.css", "harnessplay.mjs", "harnessboard.mjs", "harness-roster.json",
                 "harness-journeys.json", "harness-strings.json"):
        status, body = fetch(f"/{name}")
        assert status == 200 and body, name


def test_recorded_rebuild_player_serves_its_record_and_spark_media(server):
    """The replay plays on the Spark's 3D hall: one GLB joining the seventeen stage models, a record of which
    pieces stand at each stage, and every tested round's own load colours and re-run gravity and shake paths.
    The stage stills stay as the picture when a browser cannot draw 3D."""
    status, page = get(server, "/rebuild.html")
    assert status == 200 and b"rebuild.mjs" in page and b"hall-view" in page
    status, payload = get(server, "/rebuild-record.json")
    record = json.loads(payload)
    assert status == 200 and record["measured"]["adopted"] is True
    assert [step["step"] for step in record["steps"]] == list(range(1, 146))
    assert len(record["physics_protocol"]["shake_path_mm"]) == 144
    for frame in {chapter["frame"] for chapter in record["chapters"]}:
        status, image = get(server, f"/rebuild-{frame}.jpg")
        assert status == 200 and image.startswith(b"\xff\xd8\xff"), frame
    for frame in record["cutaway_frames"]:
        status, image = get(server, f"/rebuild-cutaway-{frame}.jpg")
        assert status == 200 and image.startswith(b"\xff\xd8\xff"), frame
    for module in ("rebuild.mjs", "rebuild-model.mjs", "rebuild-hall.mjs", "rebuild-scenes.mjs"):
        status, body = get(server, f"/{module}")
        assert status == 200 and (b"import " in body or b"export " in body), module
    status, words = get(server, "/rebuild-strings.json")
    assert status == 200 and json.loads(words)["caption.shake"]
    status, payload = get(server, "/rebuild-hall.json")
    hall = json.loads(payload)
    assert status == 200 and set(hall["stages"]) == {f"step-{s}" for s in (6, 8, 10, 16, 18, 20, 22, 28, 30, 32, 52, 54, 68, 82, 96, 110, 126)}
    assert len(hall["stages"]["step-126"]) == 4327
    status, model = get(server, "/rebuild-hall.glb")
    assert status == 200 and model[:4] == b"glTF"
    length, _ = struct.unpack_from("<II", model, 12)
    names = [node["name"] for node in json.loads(model[20:20 + length])["nodes"] if "mesh" in node]
    assert sorted(int(name[1:]) for name in names) == list(range(len(hall["pieces"])))
    for key, tested in hall["rounds"].items():
        assert tested["loads"] and tested["flow_frames"] > 0, key
        for kind in ("settle", "shake"):
            head = tested[kind]
            status, path = get(server, f"/rebuild-{kind}-{key}.gz")
            assert status == 200, (kind, key)
            assert len(gzip.decompress(path)) == head["samples"] * len(head["ids"]) * 3 * 2, (kind, key)
            assert head["fell"] == 0, (kind, key)
    status, model = get(server, "/rebuild-brackets.glb")
    assert status == 200 and model[:4] == b"glTF"
    length, chunk_type = struct.unpack_from("<II", model, 12)
    assert chunk_type == 0x4E4F534A
    bracket_names = [node.get("name", "") for node in json.loads(model[20:20 + length])["nodes"]
                     if "mesh" in node and node.get("name", "").startswith("Bracket ")]
    assert len(bracket_names) == 1372
    assert len({name.split(" | ")[0] for name in bracket_names}) == 58
    assert all(any(piece in name for name in bracket_names) for piece in
               ("base block", "tier 1 arm", "tier 1 block", "tier 2 arm", "tier 2 block", "tier 3 arm", "tier 3 block", "outrigger"))


def test_the_designs_play_beside_the_rebuilds_from_the_same_page(server):
    """rebuild.html?design=N reads the list of designs, then that design's record, its 3D and its brief's
    photograph, all from the page folder the rebuilds are served from."""
    status, payload = get(server, "/rebuild-designs.json")
    designs = json.loads(payload)["designs"]
    assert status == 200 and designs
    status, real = get(server, "/rebuild-real-hall.json")
    assert status == 200 and json.loads(real)["roof_rings"]
    for design in designs:
        n = design["n"]
        status, record = get(server, f"/rebuild-design{n}-record.json")
        assert status == 200 and json.loads(record)["source_run"] == design["run"]
        status, hall = get(server, f"/rebuild-design{n}-hall.json")
        assert status == 200 and json.loads(hall)["pieces"]
        status, model = get(server, f"/rebuild-design{n}-hall.glb")
        assert status == 200 and model[:4] == b"glTF"
        status, photo = get(server, f"/rebuild-design{n}-photo.jpg")
        assert status == 200 and photo.startswith(b"\xff\xd8\xff")


# What a browser says it can take, as Chrome sent it to the class door.
BROWSER = {"Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8", "Accept-Encoding": "gzip, deflate, br, zstd"}


def fetch(httpd, path, headers=None):
    """Status, headers and body, a 304 included, which urllib would raise."""
    conn = HTTPConnection("127.0.0.1", httpd.server_port)
    conn.request("GET", path, headers=headers or {})
    reply = conn.getresponse()
    return reply.status, dict(reply.getheaders()), reply.read()


def a_render(path, shade=0):
    """A 1280x720 picture with a render's smooth light and speckle, which PNG stores at about a megabyte."""
    from PIL import Image
    light = Image.linear_gradient("L").resize((1280, 720)).point(lambda v: min(255, v + shade))
    speckle = Image.effect_noise((1280, 720), 12)
    Image.merge("RGBA", (light, Image.blend(light, speckle, 0.3), speckle, Image.new("L", (1280, 720), 255))).save(path)
    return path.read_bytes()


def a_run(httpd, name="recorded-raise"):
    folder = httpd.driver.runs_root / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def test_a_browser_is_sent_each_render_as_webp_and_anything_else_the_png(server):
    """Measured through the class door: about 100 KB a second, so a 1 MB frame took ten
    seconds, and a replay, which shows a new frame every half second, never showed one."""
    png = a_render(a_run(server) / "raise-1.png")
    status, headers, body = fetch(server, "/api/runs/recorded-raise/files/raise-1.png", BROWSER)
    assert status == 200 and headers["Content-Type"] == "image/webp" and body[:4] == b"RIFF" and body[8:12] == b"WEBP"
    assert len(body) * 10 < len(png), f"{len(body)} bytes against the PNG's {len(png)}"
    assert headers["Vary"] == "Accept", "a cache could hand the WebP to something that asked for a PNG"
    status, headers, body = fetch(server, "/api/runs/recorded-raise/files/raise-1.png")
    assert status == 200 and headers["Content-Type"] == "image/png" and body == png


def test_the_model_its_plans_and_the_3d_library_go_compressed_to_a_browser_that_can_unpack_them(server):
    """The hall's GLB was 18 MB on the wire, three minutes at the door's rate; gzipped it is 5 MB."""
    model = server.models_root / "hall.glb"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"glTF" + b"\x00\x00\x80\x3f pieces " * 20000)
    plan = a_run(server) / "anatomy.json"
    plan.write_text(json.dumps({"pieces": {f"column {i}": {"role": "timber"} for i in range(2000)}}))
    library = exhibit.PAGE / "vendor" / "three.module.js"
    for path, source in (("/api/models/hall.glb", model), ("/api/runs/recorded-raise/files/anatomy.json", plan),
                         ("/vendor/three.module.js", library)):
        status, headers, body = fetch(server, path, BROWSER)
        assert status == 200 and headers.get("Content-Encoding") == "gzip" and headers["Vary"] == "Accept-Encoding", path
        assert gzip.decompress(body) == source.read_bytes() and len(body) * 3 < source.stat().st_size, path
        status, headers, body = fetch(server, path)
        assert status == 200 and "Content-Encoding" not in headers and body == source.read_bytes(), path


def test_a_browser_that_holds_a_file_is_not_sent_it_again_until_it_changes(server):
    """So 重播 and a second visit cost a short reply per file, not the file."""
    import os
    picture = a_run(server) / "raise-2.png"
    a_render(picture)
    path = "/api/runs/recorded-raise/files/raise-2.png"
    status, headers, _ = fetch(server, path, BROWSER)
    held = headers["ETag"]
    assert status == 200 and headers["Cache-Control"] == "no-cache"
    status, headers, body = fetch(server, path, {**BROWSER, "If-None-Match": held})
    assert status == 304 and body == b"" and headers["ETag"] == held
    status, _, body = fetch(server, path, {"If-None-Match": held})
    assert status == 200 and body == picture.read_bytes(), "the WebP's tag must not stand for the PNG"
    changed = a_render(picture, shade=40)
    later = picture.stat().st_mtime_ns + 2_000_000_000
    os.utime(picture, ns=(later, later))
    status, headers, body = fetch(server, path, {**BROWSER, "If-None-Match": held})
    assert status == 200 and headers["ETag"] != held and body[:4] == b"RIFF", "a live run rewrote the file"
    assert len(changed) > len(body)


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="making a film needs ffmpeg")
def test_a_film_is_sent_light_and_ready_to_play_at_once(server):
    """Blender's films keep their index at the end, so a browser had the whole 16 MB tour before its first
    frame. The copy sent starts with its index, and is smaller; a file ffmpeg cannot read goes as it is."""
    import subprocess
    film = a_run(server) / "raise.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "3", "-c:v", "libx264", "-crf", "8", "-pix_fmt", "yuv420p", str(film)], check=True, timeout=120)
    original = film.read_bytes()
    assert original.find(b"moov") > original.find(b"mdat"), "the made film should start the way Blender's do"
    status, headers, body = fetch(server, "/api/runs/recorded-raise/files/raise.mp4", BROWSER)
    assert status == 200 and headers["Content-Type"] == "video/mp4"
    assert 0 < body.find(b"moov") < body.find(b"mdat") and len(body) < len(original)
    (a_run(server) / "broken.mp4").write_bytes(b"not a film " * 500)
    status, headers, body = fetch(server, "/api/runs/recorded-raise/files/broken.mp4", BROWSER)
    assert status == 200 and body == b"not a film " * 500


def test_a_lighter_copy_is_made_once_however_many_ask_for_it_at_once():
    """Code review: a request arriving just as another finished could make the copy again
    (a second ffmpeg run for a film) and count its bytes twice, so the store emptied itself early."""
    from studio.showpiece.delivery import Made
    made, calls, answers, go = Made(limit=100), [], [], threading.Event()

    def make():
        calls.append(1)
        go.wait(5)
        return b"x" * 10
    askers = [threading.Thread(target=lambda: answers.append(made.get("film", make))) for _ in range(8)]
    for asker in askers:
        asker.start()
    go.set()
    for asker in askers:
        asker.join(5)
    assert len(calls) == 1 and answers == [b"x" * 10] * 8 and made.size == 10
    for name in ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"):
        made.get(name, lambda: b"y" * 10)
    assert made.size <= 100 and made.size == sum(len(v or b"") for v in made.kept.values()), "what is kept is what is counted"


def test_a_browser_holding_the_film_is_answered_without_making_it_again(server, monkeypatch):
    """After a restart nothing made is left in memory; a browser asking "is mine current?" is told so
    at once, not after the film is encoded again."""
    from studio.showpiece import delivery
    made = []
    monkeypatch.setitem(delivery.MAKERS, "film", (lambda path: made.append(path) or b"light film", "video/mp4"))
    (a_run(server) / "raise.mp4").write_bytes(b"a heavy film " * 1000)
    status, headers, body = fetch(server, "/api/runs/recorded-raise/files/raise.mp4")
    assert status == 200 and body == b"light film" and len(made) == 1
    monkeypatch.setattr(delivery, "MADE", delivery.Made())       # the studio restarted
    status, headers, body = fetch(server, "/api/runs/recorded-raise/files/raise.mp4", {"If-None-Match": headers["ETag"]})
    assert status == 304 and body == b"" and len(made) == 1


def test_a_run_request_larger_than_the_class_reads_is_refused_unread(server):
    """The classroom's cap reaches the showpiece's one route that reads a body (code review)."""
    conn = HTTPConnection("127.0.0.1", server.server_port)
    conn.request("POST", "/api/runs", body=b"", headers={"Content-Type": "application/json", "Content-Length": str(40 * 2 ** 20)})
    reply = conn.getresponse()
    assert reply.status == 400 and json.loads(reply.read())["code"] == "too_large"
    conn = HTTPConnection("127.0.0.1", server.server_port)
    conn.request("POST", "/api/runs", body=b"{not json", headers={"Content-Type": "application/json"})
    reply = conn.getresponse()
    assert reply.status == 400, "a body that is no JSON is the asker's mistake, not a dropped connection"
