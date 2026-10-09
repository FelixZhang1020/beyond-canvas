"""Durability and ownership of the course archive, with real disk/HTTP and fake models."""
import base64
import http.client
import io
import json
import sqlite3
import threading
import urllib.error
import urllib.request

from PIL import Image
import pytest

from studio.classroom.classroom import SessionGone
from studio.classroom.portfolio import Portfolio, CourseClosed
from studio.serve import make_server
from test_classroom import room, png, CLASS, ALLOW, GOOD, GROUNDED, CLEAN, run, outputs_of
from tests.server.test_serve import call, open_class
from test_classroom_integration import Voice


def test_course_content_survives_end_and_a_fresh_store_without_model_calls(tmp_path, room, png):
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    sid = classroom.begin({**CLASS, 'title': '光影练习 🌻'})
    did = classroom.add_drawing(sid, png)
    result = outputs_of(run(classroom, sid, did))
    folder = classroom.sessions[sid].folder
    assert result['artifact_id']
    classroom.update_settings(sid, {'lesson_intent': 'Read the light'})
    classroom.complete_course(sid)
    assert not folder.exists(), 'transient working copies are still released'
    assert sid not in classroom.sessions
    reopened = Portfolio(tmp_path / 'history.sqlite3')
    course = reopened.course(sid)
    assert course['title'] == '光影练习 🌻' and course['ended_at']
    assert course['lesson_intent'] == 'Read the light'
    assert reopened.drawing(sid, did)[0] == png
    saved = reopened.activity(sid, result['artifact_id'])['outputs']
    assert saved['text'] == result['text'] and saved['question'] == result['question']
    assert len(classroom.client.prompts) == 4, 'reading history never re-runs inference'
    with pytest.raises(KeyError):
        classroom.drawing(sid, did)
    with pytest.raises(KeyError):
        reopened.drawing('another-course', did)


def test_confirmed_words_remain_even_when_the_response_is_refused(tmp_path, room, png):
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    try:
        sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
        conversation = classroom._conversation(classroom.sessions[sid], did)
        from studio.conversation.conversation import Beat
        # The child is answering something: a turn sent before the studio has opened is
        # refused outright and recorded nowhere (tests/classroom/test_class_turn.py). What this
        # test is about is the REPLY being refused after a real question.
        conversation.opening = 'I see a dog. Where is it going?'
        conversation.reply = lambda *args, **kwargs: Beat('reply', 'request', refused='Try again', reason_code='rubric_failed')
        events = run(classroom, sid, did, {'transcript': 'The dog says <hello> 🌻.'})
        assert any(data.get('status') == 'stopped' for _, data in events)
        activities = classroom.portfolio.course(sid)['activities']
        assert activities[0]['skill'] == 'confirmed-words'
        assert activities[0]['summary']['text'] == 'The dog says <hello> 🌻.'
        assert activities[1]['summary']['reason_code'] == 'rubric_failed'
    finally:
        classroom.close()


def test_archived_media_and_confirmed_book_ending_reload_exactly(tmp_path, png):
    store = Portfolio(tmp_path / 'history.sqlite3'); store.begin('one', 'sketch', 'zh', '')
    store.add_drawing('one', 'art', png, 'image/png')
    mesh = {'scene': {'kind': 'mesh', 'vertices': [0.1, 0.2, 0.3], 'faces': [0, 1, 2]}}
    store.record('one', 'mesh', 'sketch-to-3d', ['art'], mesh)
    store.record('one', 'book', 'drawings-to-storybook', ['art'], {'pages': [{'drawing_id': 'art', 'text': '孩子的原话。'}]})
    store.ending('one', 'book', '他们找到了一片花园 🌻。'); store.end('one')
    reopened = Portfolio(store.path)
    assert reopened.activity('one', 'mesh')['outputs'] == mesh
    assert reopened.activity('one', 'book')['ending'] == '他们找到了一片花园 🌻。'
    assert 'vertices' not in json.dumps(reopened.course('one')), 'detail listings must not load heavy results'
    for sid, aid, text, error in [('other', 'book', 'Hi', KeyError), ('one', 'mesh', 'Hi', ValueError),
                                   ('one', 'book', '', ValueError), ('one', 'book', '你' * 2001, ValueError)]:
        with pytest.raises(error): reopened.ending(sid, aid, text)
    assert reopened.activity('one', 'book')['ending'] == '他们找到了一片花园 🌻。'


def test_a_course_keeps_one_storybook_and_a_failed_replacement_keeps_the_old_one(tmp_path):
    store = Portfolio(tmp_path / 'history.sqlite3')
    store.begin('one', 'colour', 'zh', '')
    store.begin('other', 'colour', 'zh', '')
    first = {'pages': [{'drawing_id': 'art', 'text': '花园开始了。'}]}
    store.record('one', 'first', 'drawings-to-storybook', ['art'], first)
    store.ending('one', 'first', '孩子写下的结尾。')
    store.record('other', 'other-book', 'drawings-to-storybook', ['art'], first)
    store.record('one', 'latest', 'drawings-to-storybook', ['art'], first)
    assert [a['id'] for a in store.course('one')['activities'] if a['summary']['kind'] == 'book'] == ['latest']
    assert store.activity('one', 'latest')['ending'] == '孩子写下的结尾。'
    with pytest.raises(KeyError):
        store.activity('one', 'first')
    assert store.activity('other', 'other-book')['outputs'] == first

    store.record('one', 'text', 'confirmed-words', ['art'], {'text': '保留其他成果。'})
    with pytest.raises(sqlite3.IntegrityError):
        store.record('one', 'text', 'drawings-to-storybook', ['art'], first)
    assert store.activity('one', 'latest')['ending'] == '孩子写下的结尾。'

    revised = {'pages': [{'drawing_id': 'art', 'text': '新的故事。'}]}
    store.record('one', 'revised', 'drawings-to-storybook', ['art'], revised)
    assert [a['id'] for a in store.course('one')['activities'] if a['summary']['kind'] == 'book'] == ['revised']
    assert store.activity('one', 'revised')['ending'] == ''
    assert store.activity('one', 'text')['outputs']['text'] == '保留其他成果。'


def test_a_teacher_turned_3d_view_is_kept_with_the_model_and_the_checks_own_record(tmp_path, png):
    store = Portfolio(tmp_path / 'history.sqlite3'); store.begin('one', 'sketch', 'zh', '')
    store.add_drawing('one', 'art', png, 'image/png')
    check = {'status': 'matched', 'method': 'render-and-compare-v1', 'selections': [{'phase': 'coarse', 'view': 7}]}
    scene = {'version': 1, 'method': 'cloud-glb', 'model': 'trellis2', 'glb': 'Z2xURg==', 'camera_base': [150, 65],
             'camera_calibration': check}
    store.record('one', 'toy', 'sketch-to-3d', ['art'], {'scene': scene})
    store.record('one', 'book', 'drawings-to-storybook', ['art'], {'pages': []})
    store.view('one', 'toy', [31.4, 62.6])
    store.view('one', 'toy', [-179.6, 70])
    saved = Portfolio(store.path).activity('one', 'toy')['outputs']['scene']
    assert saved['camera_base'] == [-180, 70] and saved['glb'] == 'Z2xURg=='
    assert saved['camera_calibration'] == {'status': 'teacher', 'check': check}, 'a second turn keeps the first check'
    for aid, base, error in [('toy', [200, 70], ValueError), ('toy', [0, 0.4], ValueError), ('toy', ['0', 70], ValueError),
                             ('toy', [0, 179.6], ValueError), ('toy', [float('nan'), 70], ValueError),
                             ('toy', [float('inf'), 70], ValueError),
                             ('toy', [0], ValueError), ('toy', None, ValueError), ('book', [0, 70], ValueError),
                             ('gone', [0, 70], KeyError)]:
        with pytest.raises(error): store.view('one', aid, base)
    store.end('one')
    with pytest.raises(CourseClosed): store.view('one', 'toy', [0, 70])
    assert Portfolio(store.path).activity('one', 'toy')['outputs']['scene']['camera_base'] == [-180, 70]


def test_a_legacy_sketch_study_keeps_the_same_teacher_chosen_angle(tmp_path, png):
    store = Portfolio(tmp_path / 'history.sqlite3'); store.begin('one', 'sketch', 'zh', '')
    store.add_drawing('one', 'art', png, 'image/png')
    scene = {'version': 1, 'method': 'geometric-approximation',
             'camera': {'azimuth': 0, 'elevation': 35, 'distance': 8, 'fov': 40, 'target': [0, 0, 0]},
             'objects': [{'kind': 'box', 'position': [0, 1, 0], 'size': [2, 2, 2], 'yaw': 0}]}
    store.record('one', 'toy', 'sketch-to-3d', ['art'], {'scene': scene})
    store.view('one', 'toy', [42.4, 50.7])
    saved = Portfolio(store.path).activity('one', 'toy')['outputs']['scene']
    assert saved['camera']['azimuth'] == 42 and saved['camera']['elevation'] == 51
    assert saved['objects'] == scene['objects']
    with pytest.raises(ValueError): store.view('one', 'toy', [0, 81])
    assert Portfolio(store.path).activity('one', 'toy')['outputs']['scene']['camera']['elevation'] == 51


def test_search_pagination_unicode_rename_and_parameterized_queries(tmp_path, png):
    store = Portfolio(tmp_path / 'history.sqlite3')
    for i in range(26): store.begin(str(i), 'colour', 'zh', '', f'花园 {i}')
    store.begin('sketch', 'sketch', 'en', 'Light', '100% light')
    first = store.courses(entrance='colour'); second = store.courses(entrance='colour', offset=24)
    assert len(first['items']) == 24 and first['next_offset'] == 24
    assert len(second['items']) == 2 and second['next_offset'] is None
    assert not set(i['id'] for i in first['items']) & set(i['id'] for i in second['items'])
    assert store.courses('%')['total'] == 1
    store.rename('sketch', '光影 🌻' * 20)
    assert store.courses('🌻')['total'] == 1
    assert store.courses("' OR 1=1 --")['total'] == 0
    with pytest.raises(ValueError): store.rename('sketch', '你' * 121)
    with pytest.raises(ValueError): store.rename('sketch', '')
    with pytest.raises(KeyError): store.rename('missing', 'Another')
    store.add_drawing('sketch', 'image', png, 'image/png')
    thumbnail, mime = store.drawing('sketch', 'image', True)
    assert mime == 'image/jpeg'
    assert max(Image.open(io.BytesIO(thumbnail)).size) <= 560


def test_failed_end_save_keeps_the_live_class_and_its_art(tmp_path, room, png, monkeypatch):
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
    with monkeypatch.context() as patch:
        patch.setattr(classroom.portfolio, 'end', lambda _: (_ for _ in ()).throw(sqlite3.OperationalError('disk full')))
        with pytest.raises(sqlite3.OperationalError): classroom.complete_course(sid)
        assert classroom.drawing(sid, did)[0] == png
    classroom.complete_course(sid)
    assert classroom.portfolio.course(sid)['ended_at']


def test_http_history_is_durable_scoped_and_same_origin(tmp_path, room, png):
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3'); classroom.voice = Voice()
    server = make_server(classroom, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        sid = open_class(base); did = classroom.add_drawing(sid, png)
        classroom.portfolio.record(sid, 'book', 'drawings-to-storybook', [did], {'pages': []})
        assert call(base, 'GET', '/api/courses')[1]['items'][0]['active']
        assert call(base, 'PATCH', f'/api/session/{sid}/drafts', {'drafts': {did: '草稿 🌻'}})[0] == 204
        assert call(base, 'GET', f'/api/courses/{sid}')[1]['drafts'] == {did: '草稿 🌻'}
        call(base, 'DELETE', f'/api/session/{sid}')
        assert classroom.portfolio.course(sid)['ended_at'] is None
        assert call(base, 'GET', f'/api/courses/{sid}/drawings/{did}')[1] == png
        assert call(base, 'GET', '/api/courses')[1]['items'][0]['active'] is False
        call(base, 'PATCH', f'/api/courses/{sid}', {'title': 'A saved garden'})
        call(base, 'PATCH', f'/api/courses/{sid}/activities/book/ending', {'text': 'The end.'})
        assert call(base, 'GET', f'/api/courses/{sid}/activities/book')[1]['ending'] == 'The end.'
        classroom.portfolio.record(sid, 'toy', 'sketch-to-3d', [did], {'scene': {'method': 'cloud-glb', 'glb': 'x'}})
        assert call(base, 'PATCH', f'/api/courses/{sid}/activities/toy/view', {'camera_base': [45, 65]})[0] == 204
        assert call(base, 'GET', f'/api/courses/{sid}/activities/toy')[1]['outputs']['scene']['camera_base'] == [45, 65]
        # A browser gets the large result compressed, can revalidate it, and a
        # client without gzip support still receives the same JSON.
        classroom.portfolio.record(sid, 'large', 'sketch-to-3d', [did],
                                   {'scene': {'method': 'geometric-approximation', 'solids': 'x' * 200000}})
        route = base + f'/api/courses/{sid}/activities/large'
        request = urllib.request.Request(route, headers={'Accept-Encoding': 'gzip'})
        with urllib.request.urlopen(request) as reply:
            import gzip
            packed = reply.read(); tag = reply.headers['ETag']
            assert reply.headers['Content-Encoding'] == 'gzip'
            assert reply.headers['Cache-Control'] == 'private, no-cache'
            assert len(packed) < 5000
            assert json.loads(gzip.decompress(packed))['outputs']['scene']['solids'] == 'x' * 200000
        request = urllib.request.Request(route, headers={'Accept-Encoding': 'gzip', 'If-None-Match': tag})
        with pytest.raises(urllib.error.HTTPError) as error: urllib.request.urlopen(request)
        assert error.value.code == 304
        # The gzipped copy's tag does not stand for the plain one (code review).
        with urllib.request.urlopen(urllib.request.Request(route, headers={'If-None-Match': tag})) as reply:
            assert reply.status == 200 and reply.headers.get('Content-Encoding') is None
            assert json.loads(reply.read())['outputs']['scene']['solids'] == 'x' * 200000
        assert call(base, 'GET', f'/api/courses/{sid}/activities/large')[1]['outputs']['scene']['solids'] == 'x' * 200000
        # A model goes as a file of its own, which the page fetches apart (studio/server/media_links.py).
        model = b'glTF' + bytes(range(256)) * 100
        classroom.portfolio.record(sid, 'model', 'sketch-to-3d', [did], {'scene': {
            'method': 'cloud-glb', 'glb': base64.b64encode(model).decode()}})
        address = call(base, 'GET', f'/api/courses/{sid}/activities/model')[1]['outputs']['scene']['glb']
        assert address.startswith(f'/api/courses/{sid}/activities/model/media/scene.glb?v=')
        assert call(base, 'GET', address)[1] == model
        assert call(base, 'GET', f'/api/courses/{sid}')[1]['title'] == 'A saved garden'
        _, pcm = call(base, 'POST', f'/api/courses/{sid}/speech', {'text': 'The end.'})
        assert json.loads(pcm.splitlines()[-1])['type'] == 'done'
        for path in ['/api/courses/missing', f'/api/courses/wrong/drawings/{did}',
                     '/api/courses/wrong/activities/book']:
            with pytest.raises(urllib.error.HTTPError) as error: call(base, 'GET', path)
            assert error.value.code == 404
        request = urllib.request.Request(base + f'/api/courses/{sid}', method='PATCH',
            data=b'{"title":"cross-origin"}', headers={'Origin': 'https://other.invalid', 'Content-Type': 'application/json'})
        with pytest.raises(urllib.error.HTTPError) as error: urllib.request.urlopen(request)
        assert error.value.code == 403
        assert classroom.portfolio.course(sid)['title'] == 'A saved garden'
    finally:
        server.shutdown(); server.server_close(); classroom.close()


def test_completed_course_rejects_every_content_write_until_reopened(tmp_path, png):
    store = Portfolio(tmp_path / 'history.sqlite3')
    store.begin('one', 'colour', 'zh', '', '原来的课程')
    store.add_drawing('one', 'art', png, 'image/png')
    store.record('one', 'book', 'drawings-to-storybook', ['art'], {'pages': []})
    store.end('one')
    before = store.course('one')
    writes = [lambda: store.rename('one', '新的名称'),
              lambda: store.settings('one', 'en', 'Light'),
              lambda: store.add_drawing('one', 'new-art', png, 'image/png'),
              lambda: store.record('one', 'new-result', 'art-feedback', ['art'], {'text': 'Hello'}),
              lambda: store.ending('one', 'book', '孩子确认的结尾 🌻。')]
    for write in writes:
        with pytest.raises(CourseClosed): write()
    assert store.course('one') == before
    assert store.drawing('one', 'art')[0] == png
    assert store.activity('one', 'book')['ending'] == ''
    store.reopen('one')
    for write in writes: write()
    after = store.course('one')
    assert after['ended_at'] is None and after['title'] == '新的名称'
    assert len(after['drawings']) == 2 and len(after['activities']) == 2
    assert store.activity('one', 'book')['ending'] == '孩子确认的结尾 🌻。'


def test_leaving_and_server_shutdown_keep_courses_open_and_restore_content(tmp_path, room, png):
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    course_id = classroom.begin(CLASS); did = classroom.add_drawing(course_id, png)
    classroom.portfolio.record(course_id, 'opening', 'art-feedback', [did],
                               {'beat': 'opening', 'text': 'A dog.', 'question': 'Where is it going?'})
    classroom.portfolio.record(course_id, 'words', 'confirmed-words', [did], {'text': 'To the stars 🌻.'})
    classroom.end(course_id)
    assert classroom.portfolio.course(course_id)['ended_at'] is None
    restored = classroom.edit_course(course_id); sid = restored['session_id']
    assert sid != course_id and restored['course']['id'] == course_id
    assert classroom.drawing(sid, did)[0] == png
    assert classroom.sessions[sid].transcripts[did] == 'To the stars 🌻.'
    conversation = classroom._conversation(classroom.sessions[sid], did)
    assert 'Where is it going?' in conversation.opening
    assert conversation.verdict is None, 'restored artwork is screened again before new inference'
    # A second tab gets a new editor. A delayed unload from the first cannot close it.
    newer = classroom.edit_course(course_id)['session_id']
    assert newer != sid and classroom.end(sid) is False
    assert classroom.drawing(newer, did)[0] == png
    classroom.close()
    assert classroom.portfolio.course(course_id)['ended_at'] is None
    assert classroom.portfolio.courses()['total'] == 1
    assert not classroom.client.prompts, 'restoring content makes no model calls'


def test_old_request_cannot_publish_into_a_reopened_course(tmp_path, room, png):
    from studio.classroom.classroom import RequestCancelled
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    course_id = classroom.begin(CLASS); did = classroom.add_drawing(course_id, png)
    rid = classroom.request(course_id, 'art-feedback', [did], {})['request_id']
    request = classroom.requests[rid]
    classroom.complete_course(course_id)
    sid = classroom.edit_course(course_id, reopen=True)['session_id']
    with pytest.raises(RequestCancelled):
        classroom._publish(request, 'done', {'outputs': {'text': 'A late response'}})
    with pytest.raises(RequestCancelled):
        classroom._record_request(request, rid + '-words', 'confirmed-words', {'text': 'Late words'})
    assert classroom.portfolio.course(course_id)['activities'] == []
    fresh_id = classroom.request(sid, 'art-feedback', [did], {})['request_id']
    classroom._publish(classroom.requests[fresh_id], 'done', {'outputs': {'text': 'New editor'}})
    assert classroom.portfolio.course(course_id)['activities'][0]['summary']['text'] == 'New editor'


def test_http_complete_read_only_and_explicit_reopen_keep_the_same_course(tmp_path, room, png):
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3'); classroom.voice = Voice()
    server = make_server(classroom, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        course_id = open_class(base); did = classroom.add_drawing(course_id, png)
        classroom.portfolio.record(course_id, 'book', 'drawings-to-storybook', [did], {'pages': []})
        assert call(base, 'POST', f'/api/courses/{course_id}/complete', {})[0] == 204
        for method, path, body, status in [
            ('PATCH', f'/api/courses/{course_id}', {'title': 'Locked'}, 409),
            ('PATCH', f'/api/courses/{course_id}/activities/book/ending', {'text': 'Locked'}, 409),
            ('POST', f'/api/courses/{course_id}/edit', {}, 409),
            ('PATCH', f'/api/session/{course_id}', {'language': 'zh'}, 404),
            ('POST', f'/api/session/{course_id}/requests', {'skill': 'art-feedback', 'drawing_ids': [did]}, 404),
        ]:
            with pytest.raises(urllib.error.HTTPError) as error: call(base, method, path, body)
            assert error.value.code == status
            if status == 409: assert json.load(error.value)['code'] == 'course_closed'
        assert call(base, 'GET', f'/api/courses/{course_id}')[1]['ended_at']
        assert call(base, 'GET', f'/api/courses/{course_id}/drawings/{did}')[1] == png
        assert call(base, 'GET', f'/api/courses/{course_id}/activities/book')[1]['ending'] == ''
        assert call(base, 'POST', f'/api/courses/{course_id}/speech', {'text': 'Saved words.'})[0] == 200
        payload = call(base, 'POST', f'/api/courses/{course_id}/reopen', {})[1]
        sid = payload['session_id']; assert sid != course_id
        assert payload['course']['ended_at'] is None
        assert call(base, 'DELETE', f'/api/session/{course_id}')[0] == 204
        assert classroom.drawing(sid, did)[0] == png
        new_did = classroom.add_drawing(sid, png)
        assert call(base, 'GET', f'/api/courses/{course_id}/drawings/{new_did}')[1] == png
        call(base, 'PATCH', f'/api/courses/{course_id}/activities/book/ending', {'text': 'New ending.'})
        assert call(base, 'GET', '/api/courses')[1]['total'] == 1
        call(base, 'DELETE', f'/api/session/{sid}')
        assert call(base, 'GET', f'/api/courses/{course_id}')[1]['ended_at'] is None
        call(base, 'POST', f'/api/courses/{course_id}/complete', {})
        assert call(base, 'GET', f'/api/courses/{course_id}')[1]['ended_at']
    finally:
        server.shutdown(); server.server_close(); classroom.close()


def test_course_actions_consume_json_before_reusing_the_http_connection(tmp_path, room):
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    course_id = classroom.begin(CLASS)
    server = make_server(classroom, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    connection = http.client.HTTPConnection(*server.server_address, timeout=3)
    try:
        for action, expected in [('complete', 204), ('edit', 409), ('reopen', 200), ('edit', 200)]:
            connection.request('POST', f'/api/courses/{course_id}/{action}', body=b'{}',
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse(); response.read()
            assert response.status == expected
            connection.request('GET', f'/api/courses/{course_id}')
            response = connection.getresponse(); body = response.read()
            assert response.status == 200, 'the previous JSON body must not prefix the next HTTP method'
            course = json.loads(body)
            assert bool(course['ended_at']) == (action == 'complete' or expected == 409)
    finally:
        connection.close(); server.shutdown(); server.server_close(); classroom.close()


def test_answer_drafts_are_durable_scoped_and_not_confirmed(tmp_path, png):
    path = tmp_path / 'drafts.sqlite3'
    store = Portfolio(path)
    store.begin('one', 'colour', 'zh', '')
    store.add_drawing('one', 'art', png, 'image/png')
    store.save_drafts('one', {'art': '未提交 🌻'})
    saved = Portfolio(path).course('one')
    assert saved['drafts'] == {'art': '未提交 🌻'}
    assert saved['activities'] == []
    with pytest.raises(ValueError):
        store.save_drafts('one', {'other-art': 'Wrong course'})
    with pytest.raises(ValueError):
        store.save_drafts('one', {'art': ['Not text']})
    assert store.course('one')['drafts'] == {'art': '未提交 🌻'}
    store.record('one', 'confirmed', 'confirmed-words', ['art'], {'text': '确认的话'})
    assert store.course('one')['drafts'] == {}
    store.end('one')
    with pytest.raises(CourseClosed):
        store.save_drafts('one', {'art': 'Closed'})


def test_drafts_require_a_current_editor_and_survive_release(tmp_path, room, png):
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / 'drafts.sqlite3')
    sid = classroom.begin(CLASS)
    did = classroom.add_drawing(sid, png)
    classroom.save_drafts(sid, {did: '未提交 🌻'})
    classroom.end(sid)
    with pytest.raises(KeyError):
        classroom.save_drafts(sid, {did: 'Stale editor'})
    course = classroom.portfolio.course(sid)
    assert course['drafts'] == {did: '未提交 🌻'}
    assert len(course['drawings']) == 1 and course['ended_at'] is None
    assert classroom.client.prompts == []


def test_a_tile_is_made_once_and_not_on_every_visit(tmp_path, png, monkeypatch):
    """The home screen asks for every tile each time it opens.

    Each one used to decode a photograph of a few megabytes, shrink it and
    re-encode it -- about 70 ms a tile, six tiles a visit, 232 requests in
    a single day, and the answer was identical every time.
    """
    store = Portfolio(tmp_path / 'history.sqlite3'); store.begin('one', 'sketch', 'zh', '')
    store.add_drawing('one', 'art', png, 'image/png')

    made = []
    original = Image.open
    monkeypatch.setattr(Image, 'open', lambda *a, **k: made.append(1) or original(*a, **k))

    first, mime = store.drawing('one', 'art', thumbnail=True)
    again, _ = store.drawing('one', 'art', thumbnail=True)
    assert again == first and mime == 'image/jpeg'
    assert len(made) == 1, f'the tile was rebuilt {len(made)} times'


def test_a_replaced_drawing_is_never_served_from_the_copy_kept(tmp_path, png):
    """Keeping it is only safe while the drawing behind it has not changed."""
    store = Portfolio(tmp_path / 'history.sqlite3'); store.begin('one', 'sketch', 'zh', '')
    store.add_drawing('one', 'art', png, 'image/png')
    before, _ = store.drawing('one', 'art', thumbnail=True)

    wider = io.BytesIO()
    Image.new('RGB', (900, 300), (12, 200, 90)).save(wider, format='PNG')
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE artwork SET image=?, created_at='2099-01-01T00:00:00Z' WHERE id='art'",
                   (wider.getvalue(),))
    after, _ = store.drawing('one', 'art', thumbnail=True)
    assert after != before, 'the old tile was served after the drawing changed'
    with Image.open(io.BytesIO(after)) as shown:
        assert shown.size[0] > shown.size[1], 'the new drawing is the wide one'


def test_a_drawing_already_in_the_browser_is_not_sent_again(tmp_path, room, png):
    """Every tile used to go out under no-store, so every visit re-fetched all of them."""
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    sid = classroom.begin({**CLASS, 'title': 'tiles'})
    did = classroom.add_drawing(sid, png)
    classroom.complete_course(sid)
    server = make_server(classroom, '127.0.0.1', 0, tmp_path / 'index.html')
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        base = f'127.0.0.1:{server.server_address[1]}'
        path = f'/api/courses/{sid}/drawings/{did}?thumbnail=1'
        connection = http.client.HTTPConnection(base, timeout=20)
        connection.request('GET', path); reply = connection.getresponse()
        body, tag = reply.read(), reply.headers.get('ETag')
        connection.close()
        assert reply.status == 200 and body and tag
        assert reply.headers.get('Cache-Control') == 'no-cache'

        connection = http.client.HTTPConnection(base, timeout=20)
        connection.request('GET', path, headers={'If-None-Match': tag})
        reply = connection.getresponse(); again = reply.read(); connection.close()
        assert reply.status == 304 and again == b''
    finally:
        server.shutdown(); server.server_close(); classroom.close()
def test_the_editor_a_second_window_displaced_learns_why_its_next_request_is_refused(tmp_path, room, png):
    """One editor per course is the rule; being able to say so is what makes it bearable.

    The displaced window is told nothing at the moment it loses the course, so it finds out
    from its next request. Answering that with a bare 404 sent the page back to the course to
    submit again, which returned it to the same dead id: one teacher was refused
    three times in ninety seconds. `SessionGone` carries a code the page can act on, and every
    other 404 stays a plain one so it cannot be mistaken for this.
    """
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    course_id = classroom.begin(CLASS); did = classroom.add_drawing(course_id, png)
    displaced = classroom.edit_course(course_id)['session_id']
    classroom.edit_course(course_id)  # a second window takes the course
    with pytest.raises(SessionGone) as caught:
        classroom.request(displaced, 'art-feedback', [did], {})
    assert caught.value.code == 'session_gone'
    assert displaced in str(caught.value), 'the refusal names the editor that is gone'
    # A drawing this class does not have is also a 404, and is nothing the page can rejoin from.
    current = classroom.course_session(course_id)
    with pytest.raises(KeyError) as other:
        classroom.request(current, 'art-feedback', ['no-such-drawing'], {})
    assert not isinstance(other.value, SessionGone)
    classroom.close()


def test_a_request_the_displaced_editor_had_running_ends_saying_the_course_opened_elsewhere(tmp_path, room, png):
    """Its stream used to close with nothing said, which the page can only read as a lost connection.

    A figure three minutes in was once cut off when a stale window took the course back, and the
    teacher was told to check her connection. The page already has the true sentence for `session_gone`;
    the studio now ends the request with that reason before closing it.
    """
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    course_id = classroom.begin(CLASS); did = classroom.add_drawing(course_id, png)
    displaced = classroom.edit_course(course_id)['session_id']
    stream = classroom.requests[classroom.request(displaced, 'art-feedback', [did], {})['request_id']].stream
    classroom.edit_course(course_id)  # a second window takes the course while the request is out
    ended = [data for name, data in stream.updates if name == 'done']
    assert ended and ended[-1]['status'] == 'stopped' and ended[-1]['reason_code'] == 'session_gone'
    assert stream.finished
    classroom.close()


def test_the_course_opened_elsewhere_still_reaches_the_page_after_the_cut_off_request_cleans_up(tmp_path, room, png):
    """Review: a request whose class was gone emptied its own stream as it finished, so it could
    beat the page to the sentence the takeover had just written, and the page read a lost connection again."""
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    course_id = classroom.begin(CLASS); did = classroom.add_drawing(course_id, png)
    displaced = classroom.edit_course(course_id)['session_id']
    started = classroom.request(displaced, 'art-feedback', [did], {})
    stream = classroom.requests[started['request_id']].stream
    answer = classroom.client.chat
    def taken_while_answering(*args, **kwargs):
        if classroom.course_session(course_id) == displaced:
            classroom.edit_course(course_id)   # a second window takes the course while the model answers
        return answer(*args, **kwargs)
    classroom.client.chat = taken_while_answering
    classroom.run_request(started['request_id'])   # the cut-off request finishes and cleans up first
    ended = [data for name, data in stream.follow() if name == 'done']   # and only then does the page read
    assert ended and ended[-1]['reason_code'] == 'session_gone'
    classroom.close()


def test_a_saved_figure_is_drawn_as_a_picture_for_its_card(tmp_path, room, png):
    """Operator: the figure's card in 让画动起来 showed an empty diamond beside the clip's picture.
    `?preview=1` on the result's own route (serve.py is at its size limit) draws the saved toy as the checks do."""
    from tests.making.test_figure import DOG
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / 'history.sqlite3')
    server = make_server(classroom, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        sid = open_class(base); did = classroom.add_drawing(sid, png)
        classroom.portfolio.record(sid, 'toy', 'painting-to-figure', [did], {'figure': DOG, 'language': 'en'})
        classroom.portfolio.record(sid, 'book', 'drawings-to-storybook', [did], {'pages': []})
        route = base + f'/api/courses/{sid}/activities/toy?preview=1'
        with urllib.request.urlopen(route) as reply:
            picture, tag = reply.read(), reply.headers['ETag']
            assert reply.headers['Content-Type'] == 'image/png' and picture[:8] == b'\x89PNG\r\n\x1a\n'
        with Image.open(io.BytesIO(picture)) as image:
            assert len(image.convert('RGB').getcolors(1 << 20)) > 20, 'a toy, not an empty background'
        with pytest.raises(urllib.error.HTTPError) as again:
            urllib.request.urlopen(urllib.request.Request(route, headers={'If-None-Match': tag}))
        assert again.value.code == 304, 'a saved toy never changes, so a card drawn again costs nothing'
        with pytest.raises(urllib.error.HTTPError) as other:
            urllib.request.urlopen(base + f'/api/courses/{sid}/activities/book?preview=1')
        assert other.value.code == 404, 'only a figure has a picture of itself'
    finally:
        server.shutdown(); server.server_close(); classroom.close()
