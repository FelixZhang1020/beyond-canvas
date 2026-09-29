"""A saved clip or book picture reaches the page as a file of its own (operator: "voice loading and
video loading are still slow").

Until then each travelled inside its result as text: a third bigger than the file, nothing shown until all of it
had arrived, and nothing kept, so every look downloaded it again, and a book carried every page's clip at once.
The link from the Spark measured 7 to 67 KB/s at the time.
"""
import base64
import threading
import urllib.error
import urllib.request

import pytest

from studio.classroom.portfolio import Portfolio
from studio.serve import make_server
from studio.server import media_links
from tests.classroom.test_classroom import png, room  # noqa: F401
from tests.server.test_serve import call, open_class

CLIP = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 200
PICTURE = b"\xff\xd8\xff\xe0" + bytes(range(256)) * 100


def uri(kind, data):
    return f"data:{kind};base64," + base64.b64encode(data).decode()


def test_large_clips_and_book_pictures_become_addresses_and_everything_else_stays():
    outputs = {"video_url": uri("video/mp4", CLIP), "scene_description": "a fox in a boat",
               "pages": [{"drawing_id": "d1", "text": "One.", "video_url": uri("video/mp4", CLIP),
                          "picture_url": uri("image/jpeg", PICTURE)}, {"drawing_id": "d2", "text": "Two."}],
               "pictures": [{"drawing_id": "d1", "style": "clay", "url": uri("image/jpeg", PICTURE)}],
               "keyframe": {"kind": "keyframe", "image": uri("image/png", PICTURE)},
               "small": {"video_url": uri("video/mp4", b"tiny")}}
    sent = media_links.detach(outputs, "/api/courses/c1/activities/a1")
    assert sent["video_url"].startswith("/api/courses/c1/activities/a1/media/video_url?v=")
    assert sent["pages"][0]["video_url"].startswith("/api/courses/c1/activities/a1/media/pages.0.video_url?v=")
    assert sent["pages"][0]["picture_url"].startswith("/api/courses/c1/activities/a1/media/pages.0.picture_url?v=")
    assert sent["pictures"][0]["url"].startswith("/api/courses/c1/activities/a1/media/pictures.0.url?v=")
    assert sent["keyframe"] == outputs["keyframe"], "the page reads a still pose's picture as it is"
    assert sent["small"] == outputs["small"], "a small one costs less inside than a request of its own"
    assert sent["pages"][1] == outputs["pages"][1] and sent["scene_description"] == "a fox in a boat"
    assert outputs["video_url"].startswith("data:"), "the saved result itself is not changed"
    changed = dict(outputs, video_url=uri("video/mp4", CLIP[::-1]))
    assert media_links.detach(changed, "/x")["video_url"] != media_links.detach(outputs, "/x")["video_url"], \
        "a clip made again gets a new address, so a browser never plays the old one it kept"


def test_an_address_gives_back_its_file_and_nothing_else():
    outputs = {"pages": [{"video_url": uri("video/mp4", CLIP), "picture_url": uri("image/jpeg", PICTURE)}],
               "keyframe": {"image": uri("image/png", PICTURE)}}
    assert media_links.media(outputs, "pages.0.video_url") == (CLIP, "video/mp4")
    assert media_links.media(outputs, "pages.0.picture_url") == (PICTURE, "image/jpeg")
    for wrong in ("keyframe.image", "pages.3.video_url", "pages.0.text", "pages", "video_url", "pages.x.video_url"):
        with pytest.raises(KeyError):
            media_links.media(outputs, wrong)


def test_a_saved_clip_is_played_from_its_own_address_as_it_arrives_and_kept(tmp_path, room, png):
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    server = make_server(classroom, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        sid = open_class(base); did = classroom.add_drawing(sid, png)
        classroom.portfolio.record(sid, "clip", "painting-to-animation", [did], {"video_url": uri("video/mp4", CLIP)})
        address = call(base, "GET", f"/api/courses/{sid}/activities/clip")[1]["outputs"]["video_url"]
        assert address.startswith(f"/api/courses/{sid}/activities/clip/media/video_url?v=")
        with urllib.request.urlopen(base + address) as reply:
            assert reply.read() == CLIP and reply.headers["Content-Type"] == "video/mp4"
            assert reply.headers["Accept-Ranges"] == "bytes"
            assert reply.headers["Cache-Control"] == "private, max-age=31536000, immutable"
            tag = reply.headers["ETag"]
        with urllib.request.urlopen(urllib.request.Request(base + address, headers={"Range": "bytes=10-109"})) as reply:
            assert reply.status == 206 and reply.read() == CLIP[10:110]
            assert reply.headers["Content-Range"] == f"bytes 10-109/{len(CLIP)}"
        with urllib.request.urlopen(urllib.request.Request(base + address, headers={"Range": "bytes=-16"})) as reply:
            assert reply.status == 206 and reply.read() == CLIP[-16:], "the end first, where a clip may keep its index"
        with pytest.raises(urllib.error.HTTPError) as beyond:
            urllib.request.urlopen(urllib.request.Request(base + address, headers={"Range": f"bytes={len(CLIP)}-"}))
        assert beyond.value.code == 416
        with pytest.raises(urllib.error.HTTPError) as held:
            urllib.request.urlopen(urllib.request.Request(base + address, headers={"If-None-Match": tag}))
        assert held.value.code == 304
        with pytest.raises(urllib.error.HTTPError) as other:
            urllib.request.urlopen(base + "/api/courses/wrong/activities/clip/media/video_url")
        assert other.value.code == 404, "only the class that made it can be asked for it"
    finally:
        server.shutdown(); server.server_close(); classroom.close()


def test_a_class_job_sends_its_clip_as_an_address_the_moment_it_is_done(tmp_path, room, png, monkeypatch):
    """A job the class is running, not only a saved one (operator: a storybook stood at "checking" for minutes
    after the studio had finished, because its seven pictures travelled inside the "done", 2.2 MB over the
    class's link). The result is saved first, so the address answers as soon as the page asks. The test's clip
    is a few KB, under the size that stays inside, so that size is set to nothing here."""
    from tests.classroom.test_classroom import ALLOW, outputs_of
    from tests.making.test_animation import CLEAN, Editor
    monkeypatch.setattr(media_links, "SMALL", 0)
    classroom = room([ALLOW] * 6 + [CLEAN], editor=Editor().slot())
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    server = make_server(classroom, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        sid = open_class(base); did = classroom.add_drawing(sid, png)
        started = classroom.request(sid, "painting-to-animation", [did], {"hint": "lift one paw"})
        classroom.run_request(started["request_id"])
        address = outputs_of(list(classroom.follow(started["request_id"])))["video_url"]
        course = classroom.sessions[sid].course_id
        assert address.startswith(f"/api/courses/{course}/activities/{started['request_id']}/media/video_url?v=")
        saved = classroom.portfolio.activity(course, started["request_id"])["outputs"]["video_url"]
        assert saved.startswith("data:video/mp4;base64,"), "the saved result keeps the clip itself"
        with urllib.request.urlopen(base + address) as reply:
            assert reply.read() == base64.b64decode(saved.partition(",")[2])
            assert reply.headers["Content-Type"] == "video/mp4"
    finally:
        server.shutdown(); server.server_close(); classroom.close()
