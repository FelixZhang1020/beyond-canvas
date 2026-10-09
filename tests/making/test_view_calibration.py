import base64
import io
import json
import struct

from PIL import Image, ImageChops
import pytest

from studio.making import view_calibration as vc, sketch
from studio.core.errors import ModelUnavailable
from studio.providers.base import ChatResult
from studio.providers.media import MediaResult, MediaSlot


def model_glb(mutator=None):
    vertices = [(0., 0., 0.), (2., 0., 0.), (0., 1., 0.), (0., 0., 3.)]
    binary = struct.pack('<12f', *(x for v in vertices for x in v)) + struct.pack('<12H', 0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3)
    data = {'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
            'buffers': [{'byteLength': len(binary)}],
            'bufferViews': [{'buffer': 0, 'byteLength': 48}, {'buffer': 0, 'byteOffset': 48, 'byteLength': 24}],
            'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 4, 'type': 'VEC3'},
                          {'bufferView': 1, 'componentType': 5123, 'count': 12, 'type': 'SCALAR'}],
            'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1}]}]}
    if mutator:
        mutator(data)
    encoded = json.dumps(data).encode(); encoded += b' ' * (-len(encoded) % 4)
    return struct.pack('<5I', 0x46546c67, 2, 28+len(encoded)+len(binary), len(encoded), 0x4e4f534a)+encoded+struct.pack('<II', len(binary), 0x004e4942)+binary


class Vision:
    def __init__(self, replies):
        self.replies = iter(replies); self.calls = []

    def chat(self, prompt, images, **kwargs):
        self.calls.append(images)
        answer = next(self.replies)
        if isinstance(answer, Exception):
            raise answer
        return ChatResult(json.dumps(answer), 1, 1, 0, 0, 0, 'stepfun', 'step-3.7-flash')


def test_geometry_and_preview_have_real_volume_and_distinct_views():
    shape = vc.geometry(model_glb())
    assert len(shape[0]) == 4 and len(shape[1]) == 4
    assert max(p[2] for p in shape[0])-min(p[2] for p in shape[0]) == 1
    a, b = vc.render(shape, [45, 80]), vc.render(shape, [135, 80])
    assert ImageChops.difference(a, b).getbbox() is not None
    assert len(a.getcolors(240*240)) > 2
    grid = vc.sheet(shape, [[45, 80], [135, 80]])
    assert Image.open(io.BytesIO(base64.b64decode(grid.split(',')[1]))).size == (960, 268)


def test_node_parent_rotation_is_applied():
    def rotate(d):
        d['nodes'] = [{'rotation': [0, 1, 0, 0], 'children': [1]}, {'mesh': 0, 'translation': [4, 2, 0]}]
    original, _ = vc.geometry(model_glb())
    rotated, _ = vc.geometry(model_glb(rotate))
    for a, b in zip(original, rotated):
        assert b == pytest.approx((-a[0], a[1], -a[2]))


@pytest.mark.parametrize('mutator', [
    lambda d: d['accessors'][0].update(byteOffset=500),
    lambda d: d['bufferViews'][0].update(byteStride=1),
    lambda d: d['nodes'][0].update(children=[0]),
    lambda d: d['nodes'][0].update(children=[-1]),
    lambda d: d['nodes'][0].update(translation=[float('nan'), 0, 0]),
    lambda d: d['scenes'][0].update(nodes=[0, 0]),
    lambda d: d['accessors'][1].update(componentType=5126),
])
def test_bad_geometry_is_not_calibrated(mutator):
    vision = Vision([])
    out = vc.calibrate(model_glb(mutator), 'source', vision)
    assert out['camera_calibration']['status'] == 'needs_review'
    assert 'camera_base' not in out and not vision.calls


def test_matching_selects_only_rendered_angles_and_persists_evidence():
    vision = Vision([{'view': 7, 'match': 'clear'}, {'view': 4, 'match': 'clear'}, {'same_view': True}])
    out = vc.calibrate(model_glb(), 'source', vision)
    assert out['camera_base'] == [135, 80]
    assert out['camera_calibration']['status'] == 'matched'
    assert len(vision.calls) == 3 and all(images[0] == 'source' for images in vision.calls)
    assert vision.calls[0][1] != vision.calls[1][1]
    assert [s['model'] for s in out['camera_calibration']['selections']] == ['step-3.7-flash']*3


@pytest.mark.parametrize('reply', [
    {'view': 0, 'match': 'ambiguous'}, {'view': -1, 'match': 'clear'},
    {'view': 8, 'match': 'clear'}, {'view': True, 'match': 'clear'},
    {'view': 0, 'match': 'invented'}, ModelUnavailable('private service error'),
])
def test_uncertain_or_failed_matching_is_explicit_and_does_not_retry(reply):
    vision = Vision([reply])
    out = vc.calibrate(model_glb(), 'source', vision)
    assert 'camera_base' not in out
    assert out['camera_calibration']['status'] == 'needs_review'
    assert 'private service' not in str(out) and len(vision.calls) == 1


def test_reconstruct_calibrates_after_one_generation_and_saves(tmp_path):
    from studio.classroom.portfolio import Portfolio
    image = tmp_path/'source.png'; Image.new('RGB', (80, 60), 'white').save(image)
    calls = []
    class Provider:
        def make(self, body):
            calls.append(body)
            return MediaResult([], content=model_glb(), model='trellis2')
    slot = MediaSlot(Provider(), 'to_mesh', {}, {'scene_format': 'glb'})
    # The first answer is the clean-solids look (a head goes on to the 3D model), then the view check.
    vision = Vision([{'subject': 'head'}, {'view': 5, 'match': 'clear'}, {'view': 4, 'match': 'clear'}, {'same_view': True}])
    out = sketch.reconstruct(str(image), vision, slot)
    assert out['camera_base'] == [45, 80] and len(calls) == 1
    assert base64.b64decode(out['glb']) == model_glb()
    p = Portfolio(tmp_path/'p.db'); p.begin('c', 'sketch', 'zh', '')
    p.record('c', 'a', 'sketch-to-3d', [], {'scene': out})
    assert p.activity('c', 'a')['outputs']['scene'] == out
    failed = sketch.reconstruct(str(image), Vision([{'subject': 'head'}, ModelUnavailable('offline')]), slot)
    assert failed['camera_calibration']['status'] == 'needs_review'
    assert base64.b64decode(failed['glb']) == model_glb() and len(calls) == 2


GEOMETRY = {'objects': [{'kind': 'box', 'bbox': [139, 227, 477, 710]}, {'kind': 'sphere', 'bbox': [379, 412, 658, 811]},
                        {'kind': 'cylinder', 'bbox': [579, 133, 823, 658], 'top_bbox': [582, 133, 817, 200]}]}
CALIBRATION = [{'view': 5, 'match': 'clear'}, {'view': 4, 'match': 'clear'}, {'same_view': True}]


def test_a_geometry_sketch_becomes_clean_solids_without_a_3d_model_job(tmp_path):
    # Operator decision: TRELLIS.2 broke 3 of 4 geometry sketches into hollow shells.
    image = tmp_path/'source.png'; Image.new('RGB', (300, 200), 'white').save(image)
    class Never:
        def make(self, body):
            raise AssertionError('a geometry sketch must not reach the 3D model')
    vision = Vision([GEOMETRY])
    out = sketch.reconstruct(str(image), vision, MediaSlot(Never(), 'to_mesh', {}, {'scene_format': 'glb'}))
    assert out['method'] == 'geometric-approximation' and len(vision.calls) == 1
    assert [o['kind'] for o in out['objects']] == ['box', 'sphere', 'cylinder']


def test_explicit_trellis_regeneration_does_not_replace_the_selected_model_with_solids(tmp_path):
    image = tmp_path/'source.png'; Image.new('RGB', (300, 200), 'white').save(image)
    calls = []
    class Provider:
        def make(self, body):
            calls.append(body['model_choice'])
            return MediaResult([], content=model_glb(), model='trellis2')
    # The first vision call must be view calibration. A geometry detection here would
    # consume its answer and prove the selected generation mode was ignored.
    vision = Vision(CALIBRATION)
    out = sketch.reconstruct(str(image), vision, MediaSlot(Provider(), 'to_mesh', {}, {'scene_format': 'glb'}), model_choice='trellis2')
    assert out['method'] == 'cloud-glb' and out['model'] == 'trellis2'
    assert calls == ['trellis2'] and len(vision.calls) == 3


@pytest.mark.parametrize('answer', [
    {'subject': 'head'},
    {'objects': [{'kind': 'apple', 'bbox': [100, 100, 600, 800], 'stem_bbox': None}]},
    ModelUnavailable('offline'), 'not a detection', {'supported': False},
])
def test_heads_fruit_and_any_failed_check_still_go_to_trellis(tmp_path, answer):
    image = tmp_path/'source.png'; Image.new('RGB', (300, 200), 'white').save(image)
    calls = []
    class Provider:
        def make(self, body):
            calls.append(body)
            return MediaResult([], content=model_glb(), model='trellis2')
    vision = Vision([answer, *CALIBRATION])
    out = sketch.reconstruct(str(image), vision, MediaSlot(Provider(), 'to_mesh', {}, {'scene_format': 'glb'}))
    assert out['method'] == 'cloud-glb' and len(calls) == 1


def test_independent_pair_check_rejects_false_positive():
    vision = Vision([{'view': 5, 'match': 'clear'}, {'view': 4, 'match': 'clear'}, {'same_view': False}])
    out = vc.calibrate(model_glb(), 'source', vision)
    assert out['camera_calibration']['reason'] == 'verification_rejected'
    assert 'camera_base' not in out and len(vision.calls) == 3


def test_cancel_during_selection_does_not_submit_another_call():
    from studio.providers.gpu_job import cancelled_request
    vision = Vision([{'view': 5, 'match': 'clear'}])
    token = cancelled_request.set(lambda: bool(vision.calls))
    try:
        result = vc.calibrate(model_glb(), 'source', vision)
        assert len(vision.calls) == 1
        assert result['camera_calibration']['status'] == 'needs_review'
    finally:
        cancelled_request.reset(token)


def test_wrong_json_shape_preserves_model():
    result = vc.calibrate(model_glb(), 'source', Vision([['not an object']]))
    assert result['camera_calibration']['status'] == 'needs_review'


def test_classroom_caches_calibrated_scene_without_regenerating(tmp_path):
    from tests.making.test_sketch import classroom
    replies = [json.dumps({'subject': 'head'}), json.dumps({'view': 5, 'match': 'clear'}),
               json.dumps({'view': 4, 'match': 'clear'}), json.dumps({'same_view': True})]
    room, sid, did, vision, screener = classroom(tmp_path, replies)
    calls = []
    class Provider:
        def make(self, body):
            calls.append(body)
            return MediaResult([], content=model_glb(), model='trellis2')
    room.portrait = MediaSlot(Provider(), 'to_mesh', {}, {'scene_format': 'glb'})
    try:
        scenes = []
        for _ in range(2):
            request = room.request(sid, 'sketch-to-3d', [did], {'model_choice': 'auto'})
            room.run_request(request['request_id'])
            scenes.append(next(data['outputs']['scene'] for event, data in room.follow(request['request_id']) if event == 'done'))
        assert scenes[0] == scenes[1]
        assert scenes[0]['camera_base'] == [45, 80]
        assert len(calls) == 1 and len(vision.calls) == 4 and len(screener.calls) == 1
    finally:
        room.close()
