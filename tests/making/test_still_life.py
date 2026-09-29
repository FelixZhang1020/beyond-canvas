"""Measured fruit parts, bounded meshes and the existing classroom route."""
import copy
import json
import math

import pytest

from studio.making import mesh, sketch, still_life
from tests.making.test_sketch import classroom, run

DETECTIONS = [
    {"kind":"sphere", "bbox":[168,299,455,727]},
    {"kind":"box", "bbox":[420,170,736,612]},
    {"kind":"pear", "bbox":[557,343,774,785], "stem_bbox":[666,345,682,374], "neck_bbox":[635,375,700,420]},
]


def build(detections=DETECTIONS):
    fitted = sketch.fit(sketch.parse_detections(json.dumps(detections),1.5),1.5)
    return fitted, still_life.scene(fitted)


def test_pear_stays_a_measured_fruit_with_a_neck_and_stalk():
    fitted, scene = build()
    assert [o["kind"] for o in scene["objects"]] == ["sphere","box","pear"]
    pear = fitted["objects"][2]
    assert pear["source_box"][1] == .375  # corroborated stalk is excluded
    assert pear["profile"][-2][2] < max(r[2] for r in pear["profile"]) * .5
    assert pear["stem"][1][1] > pear["stem"][0][1]
    assert len(scene["mesh"]["indices"])//3 < 5000
    assert mesh.validate(scene["mesh"]) == scene["mesh"]
    # The stalk is real geometry above the body's top, not a painted line.
    assert max(scene["mesh"]["positions"][1::3]) > scene["objects"][2]["size"][1]


def test_measured_neck_width_changes_the_surface_and_stalk_can_be_absent():
    narrow = sketch.parse_detections(json.dumps(DETECTIONS),1.5)["objects"][2]
    changed = copy.deepcopy(DETECTIONS)
    changed[2].update(bbox=[557,375,774,785], neck_bbox=[615,375,720,420], stem_bbox=None)
    wide = sketch.parse_detections(json.dumps(changed),1.5)["objects"][2]
    assert wide["profile"][-2][2] > narrow["profile"][-2][2]*1.5
    assert still_life.body_points(narrow["profile"]) != still_life.body_points(wide["profile"])
    _, with_stem = build()
    _, without_stem = build(changed)
    assert len(with_stem["mesh"]["indices"]) > len(without_stem["mesh"]["indices"])


@pytest.mark.parametrize("update", [
    {"kind":"sphere"}, {"kind":"vase"}, {"neck_bbox":None},
    {"neck_bbox":[600,400,900,450]}, {"neck_bbox":[635,600,700,740]},
    {"stem_bbox":[666,345,900,374]}, {"stem_bbox":[666,600,682,690]},
    {"stem_bbox":[True,345,682,374]}, {"neck_bbox":[635,375,float('nan'),420]},
])
def test_bad_or_misclassified_parts_are_refused(update):
    doc = copy.deepcopy(DETECTIONS)
    doc[2].update(update)
    with pytest.raises(ValueError):
        sketch.parse_detections(json.dumps(doc),1.5)


def test_a_missing_part_measurement_is_not_replaced_with_a_template():
    for key in ("stem_bbox","neck_bbox"):
        doc = copy.deepcopy(DETECTIONS)
        del doc[2][key]
        with pytest.raises(ValueError):
            sketch.parse_detections(json.dumps(doc),1.5)


def test_the_mesh_transform_preserves_layout_occlusion_and_perspective():
    fitted, scene = build()
    def project(p, c):
        a = math.radians(c["elevation"])
        x,y,z = [v-t for v,t in zip(p,c["target"])]
        depth = c["distance"]-y*math.sin(a)-z*math.cos(a)
        return [x/depth,(y*math.cos(a)-z*math.sin(a))/depth]
    for before,after in zip(fitted["objects"],scene["objects"]):
        assert project(before["position"],fitted["camera"]) == pytest.approx(project(after["position"],scene["camera"]))
    sphere, box, pear = scene["objects"]
    assert sphere["position"][0] < box["position"][0] < pear["position"][0]
    assert pear["position"][2] > box["position"][2] and sphere["position"][2] > box["position"][2]


@pytest.mark.parametrize("kind", ["pear","apple","orange"])
def test_six_fruits_stay_below_the_mesh_budget(kind):
    doc = [copy.deepcopy(DETECTIONS[2]) for _ in range(6)]
    for obj in doc:
        obj["kind"] = kind
        if kind != "pear":
            obj.update(bbox=[557,375,774,785],stem_bbox=None)
    _, scene = build(doc)
    assert len(scene["mesh"]["indices"])//3 <= 16000
    assert len(json.dumps(scene).encode()) < mesh.MAX_BYTES


def test_classroom_returns_and_caches_a_mixed_mesh_without_portrait_inference(tmp_path):
    room,sid,did,writer,screener = classroom(tmp_path,[json.dumps(DETECTIONS)])
    assert room.portrait is None
    try:
        first,second = run(room,sid,did),run(room,sid,did)
        output = lambda events: next(d["outputs"]["scene"] for n,d in events if n == "done")
        assert output(first)["method"] == "parametric-still-life"
        assert output(first) == output(second)
        assert len(writer.calls) == len(screener.calls) == 1
    finally:
        room.close()


@pytest.mark.parametrize("repaired", [True,False])
def test_missing_fruit_parts_get_one_metered_recheck_and_never_an_invented_stalk(tmp_path,repaired):
    missing = copy.deepcopy(DETECTIONS)
    del missing[2]["stem_bbox"]
    room,sid,did,writer,screener = classroom(tmp_path,[json.dumps(missing),json.dumps(DETECTIONS if repaired else missing)])
    try:
        events = run(room,sid,did)
        assert len(writer.calls) == 2 and len(screener.calls) == 1
        assert any(n == "done" and "outputs" in d for n,d in events) is repaired
        if not repaired:
            assert any(d.get("reason_code") == "invalid_scene" for _,d in events)
        assert room.ledger_lines(sid)[-1]["tokens"] == 300
    finally:
        room.close()
