import json
import struct
from pathlib import Path

import httpx
import pytest

from studio.making import glb, sketch
from studio.core.errors import ModelRefused
from studio.providers.cloudmesh import CloudMeshClient
from studio.providers.media import MediaResult, MediaSlot


def tiny_glb(**changes):
    data = {'accessors':[{'count':12}], 'meshes':[{'primitives':[{'indices':0}]}]}
    data.update(changes)
    encoded=json.dumps(data).encode(); encoded += b' ' * (-len(encoded) % 4)
    return struct.pack('<5I',0x46546c67,2,20+len(encoded),len(encoded),0x4e4f534a)+encoded


def test_glb_guards():
    assert glb.validate(tiny_glb()) == 4
    bad = [b'bad', tiny_glb(images=[{'uri':'https://outside/image.png'}]),
           tiny_glb(accessors=[{'count':1050003}]), tiny_glb(extensionsRequired=['KHR_draco_mesh_compression']),
           tiny_glb(bufferViews=[{'byteLength':999999}]), tiny_glb(nodes=[{'mesh':0},{'mesh':0}])]
    for content in bad:
        with pytest.raises(ValueError): glb.validate(content)


@pytest.mark.parametrize('model', ['trellis2','pixal'])
def test_provider_single_submission_and_bounded_output(monkeypatch, model):
    monkeypatch.setenv('REPLICATE_API_KEY','test-only');monkeypatch.setenv('FALAI_API_KEY','test-only')
    calls=[]
    def handler(request):
        calls.append(request)
        if request.method=='POST':
            body=json.loads(request.content)
            assert ('version' in body) == (model=='trellis2')
            if model=='trellis2': return httpx.Response(200,json={'status':'succeeded','output':{'model_file':'https://replicate.delivery/model.glb'}})
            return httpx.Response(200,json={'status_url':'https://queue.fal.run/status','response_url':'https://queue.fal.run/result'})
        if request.url.path=='/status': return httpx.Response(200,json={'status':'COMPLETED'})
        if request.url.path=='/result': return httpx.Response(200,json={'model_glb':{'url':'https://v3.fal.media/model.glb'}})
        assert 'authorization' not in request.headers
        return httpx.Response(200,content=tiny_glb())
    client=CloudMeshClient('trellis2',client=httpx.Client(transport=httpx.MockTransport(handler)))
    result=client.make({'image':'data:image/png;base64,eA==','model_choice':model})
    assert result.content==tiny_glb() and result.model==model and not result.urls and not result.payload
    assert sum(c.method=='POST' for c in calls)==1


def test_download_rejects_redirect_to_local_and_large_length():
    def handler(request):
        return httpx.Response(302,headers={'Location':'http://127.0.0.1/private'})
    client=CloudMeshClient('trellis2',client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ModelRefused): client._download('https://replicate.delivery/model.glb')
    client._client=httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,headers={'Content-Length':str(glb.MAX_BYTES+1)})))
    with pytest.raises(ModelRefused): client._download('https://replicate.delivery/model.glb')


def test_cloud_path_uses_no_local_geometry_and_archives_model():
    class Provider:
        def make(self, body):
            assert body['model_choice']=='pixal'
            return MediaResult([],content=tiny_glb(),model='pixal')
    slot=MediaSlot(Provider(),'to_mesh',{}, {'scene_format':'glb'})
    output=sketch.reconstruct('skills/art-feedback/evals/files/dog-sun.png',None,slot,model_choice='pixal')
    assert output['method']=='cloud-glb' and output['model']=='pixal' and output['bytes']==len(tiny_glb())


def test_saved_scene_survives_reopen(tmp_path):
    from studio.classroom.portfolio import Portfolio
    store=Portfolio(tmp_path/'courses.db');store.begin('course','sketch','zh','test')
    output={'scene':glb.scene(tiny_glb(),1,'trellis2')}
    store.record('course','result','sketch-to-3d',[],output)
    restored=Portfolio(tmp_path/'courses.db').activity('course','result')
    assert restored['outputs']['scene']==output['scene']


def test_classroom_safety_and_model_cache(tmp_path):
    from tests.making.test_sketch import classroom
    # Repeated reads reuse the model; explicit regeneration must submit a fresh job.
    # Pixal3D was archived, so asking for it is refused.
    room,sid,did,vision,screener=classroom(tmp_path,[json.dumps({'subject':'head'})])
    choices=[]
    class Provider:
        def make(self, body):
            choices.append(body['model_choice'])
            return MediaResult([],content=tiny_glb(),model=body['model_choice'])
    room.portrait=MediaSlot(Provider(),'to_mesh',{}, {'scene_format':'glb'})
    try:
        for _ in range(2):
            request=room.request(sid,'sketch-to-3d',[did],{'model_choice':'trellis2'})
            room.run_request(request['request_id'])
            output=next(data['outputs']['scene'] for name,data in room.follow(request['request_id']) if name=='done')
            assert output['model']=='trellis2'
        assert choices==['trellis2'] and len(screener.calls)==1
        request=room.request(sid,'sketch-to-3d',[did],{'model_choice':'trellis2','regenerate':True})
        room.run_request(request['request_id'])
        assert choices==['trellis2','trellis2']
        with pytest.raises(ValueError, match='Pixal3D was archived'):
            room.request(sid,'sketch-to-3d',[did],{'model_choice':'pixal'})
        with pytest.raises(ValueError):room.request(sid,'sketch-to-3d',[did],{'model_choice':'unknown'})
        with pytest.raises(ValueError, match='regenerate must be a boolean'):
            room.request(sid,'sketch-to-3d',[did],{'regenerate':'true'})
    finally:room.close()


def test_safety_refusal_never_submits_cloud_mesh(tmp_path):
    from tests.making.test_sketch import classroom, run
    room,sid,did,_,screener=classroom(tmp_path,[])
    class Never:
        def make(self, body):raise AssertionError('must not reach cloud generation')
    room.portrait=MediaSlot(Never(),'to_mesh',{}, {'scene_format':'glb'})
    screener.replies=['{"verdict":"unsafe","reason":"unsafe","text_found":[]}'] * 2
    try:
        events=run(room,sid,did)
        assert any(data.get('reason_code')=='unsafe_image' for _,data in events)
    finally:room.close()
