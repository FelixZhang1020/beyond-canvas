"""Geometry, refusal and classroom integration. No live model in these tests."""
import copy
import json
import io
from pathlib import Path
from PIL import Image

import pytest

from studio.making import sketch
from studio.classroom.classroom import Classroom
from tests.conftest import FakeClient

DRAWING = Path("skills/art-feedback/evals/files/sphere-study.png")
ALLOW = '{"verdict":"allow","reason":"a drawing","text_found":[]}'
ANNOTATION = {
    "supported": True, "camera_elevation_degrees": 25, "light": [-3, 6, 5],
    "objects": [
        {"kind": "box", "box": [.14, .19, .33, .53], "proportions": [1, 1, 1], "yaw_degrees": 40},
        {"kind": "sphere", "box": [.38, .40, .28, .42], "proportions": [1, 1, 1], "yaw_degrees": 0},
        {"kind": "cylinder", "box": [.58, .12, .24, .54], "proportions": [1, 1.5, 1], "yaw_degrees": 0},
    ],
}
DETECTIONS = {"supported": True, "objects": [
    {"kind": "box", "bbox": [139,227,477,710]},
    {"kind": "sphere", "bbox": [379,412,658,811]},
    {"kind": "cylinder", "bbox": [579,133,823,658], "top_bbox": [582,133,817,200]},
]}


def test_three_shapes_survive_without_a_foreground_mask_or_texture():
    scene = sketch.fit(sketch.parse(json.dumps(ANNOTATION)), 1.5)
    assert [o["kind"] for o in scene["objects"]] == ["box", "sphere", "cylinder"]
    assert all(o["fit_error"] < .04 for o in scene["objects"])
    assert all(abs(o["position"][1] - o["size"][1]/2) < .001 for o in scene["objects"])
    assert scene["objects"][0]["position"][0] < scene["objects"][1]["position"][0] < scene["objects"][2]["position"][0]
    assert scene["objects"][1]["position"][2] > scene["objects"][2]["position"][2]
    assert "texture" not in json.dumps(scene)
    assert len(json.dumps(scene)) < 4000


def test_fit_responds_to_a_different_drawing_instead_of_a_fixed_scene():
    doc = copy.deepcopy(ANNOTATION)
    doc["objects"] = [doc["objects"][1]]
    first = sketch.fit(sketch.parse(json.dumps(doc)), 1.5)
    doc["objects"][0]["box"][0] -= .2
    second = sketch.fit(sketch.parse(json.dumps(doc)), 1.5)
    assert len(second["objects"]) == 1
    assert first["objects"][0]["position"][0] > second["objects"][0]["position"][0] + 1


def test_perspective_changes_apparent_size_with_distance():
    points = [(x,y+.5,z) for x,y,z in sketch.surface_points("box")]
    near = sketch.projected_box(points, 0, 2, 1, sketch.camera(25), 1.5)
    far = sketch.projected_box(points, 0, -2, 1, sketch.camera(25), 1.5)
    assert near[2] > far[2] * 1.3


@pytest.mark.parametrize("key,value", [
    ("kind", "person"), ("box", [0,0,0,0]), ("box", [.9,.1,.3,.3]),
    ("box", [0,0,float("nan"),.4]), ("box", [0,.1,.2]),
    ("proportions", [1,-1,1]), ("proportions", [True,1,1]),
    ("yaw_degrees", float("inf")),
])
def test_invalid_shapes_are_refused_instead_of_replaced(key, value):
    doc = copy.deepcopy(ANNOTATION)
    doc["objects"][0][key] = value
    with pytest.raises(ValueError):
        sketch.parse(json.dumps(doc))


@pytest.mark.parametrize("payload", ["[]", "{}", '{"supported":false}', '{"supported":true,"objects":[]}', '"text"'])
def test_empty_and_unsupported_answers_do_not_become_demo_geometry(payload):
    with pytest.raises(ValueError):
        sketch.parse(payload)


def test_object_count_and_light_height_are_bounded():
    for update in ({"objects": ANNOTATION["objects"] * 3}, {"light": [0,-1,0]}):
        with pytest.raises(ValueError):
            sketch.parse(json.dumps({**ANNOTATION, **update}))


def test_model_prose_and_names_are_not_passed_to_the_page():
    doc = copy.deepcopy(ANNOTATION)
    doc["name"] = doc["objects"][0]["name"] = "private drawing inscription"
    parsed = sketch.parse('```json\n' + json.dumps(doc) + '\n```')
    assert "private drawing inscription" not in json.dumps(parsed)


def classroom(tmp_path, replies, entrance="sketch"):
    writer, screener = FakeClient(replies), FakeClient([ALLOW])
    room = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": writer,
                     "vlm.director": FakeClient([]), "safety.image": screener})
    sid = room.begin({"language":"zh", "entrance":entrance})
    with Image.open(DRAWING) as image:
        png = io.BytesIO()
        image.resize((300, 200)).save(png, format="PNG")
    did = room.add_drawing(sid, png.getvalue())
    return room, sid, did, writer, screener


def run(room, sid, did):
    req = room.request(sid, "sketch-to-3d", [did], {})
    room.run_request(req["request_id"])
    return list(room.follow(req["request_id"]))


def test_classroom_screens_once_caches_scene_and_records_real_stages(tmp_path):
    room, sid, did, writer, screener = classroom(tmp_path, [json.dumps(DETECTIONS)])
    try:
        assert "sketch-to-3d" in room.health()["skills"]
        first, second = run(room,sid,did), run(room,sid,did)
        output = lambda events: next(data["outputs"]["scene"] for name,data in events if name == "done")
        assert output(first) == output(second)
        assert len(writer.calls) == len(screener.calls) == 1
        assert writer.calls[0]["max_tokens"] == sketch.MAX_TOKENS
        stages = [row for row in room.ledger_lines(sid)]
        assert [row["stage"] for row in stages] == ["studio-safety", "sketch-to-3d", "sketch-to-3d"]
        assert stages[-1]["tokens"] == 0
        assert "source_box" not in json.dumps(stages)
    finally:
        room.close()


def test_safety_block_prevents_recognition_and_remains_blocked(tmp_path):
    room, sid, did, writer, screener = classroom(tmp_path, [])
    screener.replies = ['{"verdict":"unsafe","reason":"unsafe","text_found":[]}'] * 2
    try:
        for _ in range(2):
            events = run(room,sid,did)
            stop = next(d for _,d in events if d.get("status") == "stopped")
            assert stop["stage"] == "studio-safety"
            assert stop["reason_code"] == "unsafe_image"
        assert not writer.calls
        assert len(screener.calls) == 2
    finally:
        room.close()


@pytest.mark.parametrize("reply,reason", [('{"supported":false}', "unsupported_geometry"), ('{"bad":1}', "invalid_scene")])
def test_recognition_failure_is_explained_and_not_called_a_model_outage(tmp_path, reply, reason):
    room, sid, did, writer, _ = classroom(tmp_path, [reply])
    try:
        events = run(room,sid,did)
        stop = next(d for _,d in events if d.get("status") == "stopped")
        assert stop["reason_code"] == reason
        assert not any("outputs" in d for _,d in events)
        assert len(writer.calls) == 1
    finally:
        room.close()


def test_colour_entrance_is_not_silently_treated_as_a_sketch(tmp_path):
    room, sid, did, _, _ = classroom(tmp_path, [], entrance="colour")
    try:
        with pytest.raises(ValueError, match="sketch entrance"):
            run(room,sid,did)
    finally:
        room.close()


def test_only_one_reconstruction_is_admitted_at_a_time(tmp_path):
    room, sid, did, writer, _ = classroom(tmp_path, [])
    room.sketch_slot.acquire()
    try:
        events = run(room,sid,did)
        assert any(d.get("reason_code") == "busy" for _,d in events)
        assert not writer.calls
    finally:
        room.sketch_slot.release()
        room.close()


def test_http_stream_delivers_geometry_not_an_image_or_turntable_url(tmp_path):
    import threading
    from studio.serve import make_server
    from tests.server.test_serve import call, stream

    room, sid, did, _, _ = classroom(tmp_path, [json.dumps(DETECTIONS)])
    server = make_server(room, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_address[1]}'
        _, request = call(base, 'POST', f'/api/session/{sid}/requests',
                          {'skill':'sketch-to-3d','drawing_ids':[did],'options':{}})
        events = stream(base, request['request_id'])
        out = next(d['outputs'] for name,d in events if name == 'done')
        assert len(out['scene']['objects']) == 3
        assert out['scene']['method'] == 'geometric-approximation'
        assert not any(key.endswith('_url') for key in out)
    finally:
        server.shutdown()
        server.server_close()
        room.close()


def test_boxes_written_as_fractions_are_read_as_thousandths():
    # Step 3.7 Flash answered 0.128 where the prompt asks for 128 on two of four sketches.
    fractions = json.loads(json.dumps(DETECTIONS))
    for obj in fractions["objects"]:
        for key in ("bbox", "top_bbox"):
            if key in obj:
                obj[key] = [v / 1000 for v in obj[key]]
    assert sketch.parse_detections(json.dumps(fractions), 1.5) == sketch.parse_detections(json.dumps(DETECTIONS), 1.5)


def test_tiny_whole_number_boxes_are_not_mistaken_for_fractions():
    doc = {"objects": [{"kind": "box", "bbox": [0, 0, 1, 1]}]}
    with pytest.raises(ValueError):
        sketch.parse_detections(json.dumps(doc), 1.5)


def test_top_ellipse_calibrates_camera_above_the_solid_not_below_its_top():
    annotation = sketch.parse_detections(json.dumps(DETECTIONS), 1.5)
    old, _ = sketch._fit_at_elevation(annotation, 1.5, annotation["camera_elevation_degrees"])
    assert old["camera"]["position"][1] < old["objects"][2]["size"][1]
    scene = sketch.fit(annotation, 1.5)
    assert scene["camera"]["position"][1] > max(o["size"][1] for o in scene["objects"])
    assert max(o["fit_error"] for o in scene["objects"]) < .035


@pytest.mark.parametrize("update", [
    {"bbox": [200,100,100,200]}, {"bbox": [0,0,1001,300]},
    {"bbox": [0,0,False,200]}, {"bbox": [0,0,float('inf'),300]},
    {"top_bbox": [0,0,10,10]}, {"kind": "human"},
])
def test_bad_native_detections_cannot_reach_the_fitter(update):
    doc = copy.deepcopy(DETECTIONS)
    doc["objects"][2].update(update)
    with pytest.raises(ValueError):
        sketch.parse_detections(json.dumps(doc), 1.5)


def test_native_localization_accepts_fences_and_lists_but_drops_prose():
    doc = copy.deepcopy(DETECTIONS["objects"])
    doc[0]["name"] = 'private drawing inscription'
    parsed = sketch.parse_detections('```json\n'+json.dumps(doc)+'\n```',1.5)
    assert len(parsed["objects"]) == 3
    assert "private drawing inscription" not in json.dumps(parsed)


def test_geometry_alias_is_metered_without_calling_dialogue_or_director(tmp_path):
    room, sid, did, writer, _ = classroom(tmp_path, [])
    geometry = FakeClient([json.dumps(DETECTIONS)])
    room.clients['vlm.sketch'] = geometry
    try:
        assert any('outputs' in data for _,data in run(room,sid,did))
        assert len(geometry.calls) == 1 and not writer.calls
        assert room.ledger_lines(sid)[-1]['tokens'] == 150
    finally:
        room.close()


def test_small_independent_rim_localization_error_is_unioned_not_clipped():
    doc = copy.deepcopy(DETECTIONS)
    doc["objects"][2].update(bbox=[575,136,821,659], top_bbox=[578,124,815,213])
    parsed = sketch.parse_detections(json.dumps(doc),1.5)
    cylinder = parsed["objects"][2]
    assert cylinder["box"][1] == .124
    assert cylinder["top_box"][3] == .089
    scene = sketch.fit(parsed,1.5)
    assert len(scene["objects"]) == 3
    assert max(o["fit_error"] for o in scene["objects"]) < .04
    # A top far from its object is still invalid; tolerance scales down for
    # small shapes and never exceeds 2% of the image dimension.
    doc["objects"][2]["top_bbox"][1] = 100
    with pytest.raises(ValueError, match="outside"):
        sketch.parse_detections(json.dumps(doc),1.5)
