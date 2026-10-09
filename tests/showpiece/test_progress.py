"""The exhibit's heartbeat: what a run is doing between two events, and how far a render has got."""
import json
import time

from studio.showpiece import progress


def test_expected_frames_follow_each_tools_defaults_and_arguments(tmp_path):
    assert progress.expected_frames("explode", {}, tmp_path) == 180
    assert progress.expected_frames("explode", {"seconds": 2, "fps": 10}, tmp_path) == 20
    assert progress.expected_frames("tour", {}, tmp_path) == 480
    assert progress.expected_frames("tour", {"segments": "outside,inside", "seconds-per": 1, "fps": 8}, tmp_path) == 16
    assert progress.expected_frames("settle", {}, tmp_path) == 96
    assert progress.expected_frames("flow", {}, tmp_path) == 240
    assert progress.expected_frames("raise", {}, tmp_path) is None, "no scenes.json yet"
    (tmp_path / "scenes.json").write_text(json.dumps({"scenes": [{}] * 5}))
    assert progress.expected_frames("raise", {}, tmp_path) == 5 * 30 + 30
    assert progress.expected_frames("judge", {}, tmp_path) is None
    assert progress.expected_frames("explode", {"seconds": "six"}, tmp_path) == 180, "a bad value falls back"


def test_a_heartbeat_counts_the_frames_landed_so_far(tmp_path):
    (tmp_path / "explode").mkdir()
    for i in (1, 2, 3):
        (tmp_path / "explode" / f"f{i:04d}.png").write_bytes(b"")
    (tmp_path / "explode" / "notes.txt").write_text("not a frame")
    beat = progress.heartbeat(tmp_path, {"phase": "tool", "skill": "joint-reveal", "tool": "explode",
                                         "args": {"seconds": 1, "fps": 10}, "started": time.monotonic() - 4.2})
    assert beat["frames"] == 3 and beat["newest"] == "explode/f0003.png" and beat["expected"] == 10
    assert beat["seconds"] == 4 and beat["skill"] == "joint-reveal"
    thinking = progress.heartbeat(tmp_path, {"phase": "thinking", "started": time.monotonic()})
    assert thinking["phase"] == "thinking" and "frames" not in thinking


def test_a_quick_live_run_expects_a_third_of_the_frames(tmp_path):
    from studio.showpiece import catalog
    from studio.showpiece.progress import expected_frames
    (tmp_path / "scenes.json").write_text('{"scenes": [{}, {}, {}, {}, {}]}', encoding="utf-8")
    full = expected_frames("raise", {"scenes": "scenes.json"}, tmp_path)
    quick = expected_frames("raise", catalog.quick_args(catalog.TOOLS[("raise-the-hall", "raise")], {"scenes": "scenes.json"}), tmp_path)
    assert full == 5 * 30 + 30 and quick == 5 * 10 + 10, "30 frames a second at full size, 10 when quick"
    assert expected_frames("tour", catalog.quick_args(catalog.TOOLS[("structure-tour", "tour")], {}), tmp_path) == 4 * 30, "four 3 s moves at 10 fps"
