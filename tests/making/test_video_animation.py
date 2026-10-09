"""Video output validation, screening and durable story media (no vendor calls)."""
import subprocess
import pytest
from studio.making import animation
from studio.classroom.portfolio import Portfolio
from tests.making.test_animation import CLEAN, Editor, talk
from studio.providers.media import MediaSlot

@pytest.fixture
def clip(tmp_path):
    path = tmp_path / 'clip.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=24',
                    '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True, timeout=20)
    return path.read_bytes()

def test_video_decodes_and_invalid_bytes_are_rejected(clip):
    result = animation.normalize_video(clip)
    assert result.as_dict()['kind'] == 'video'
    assert result.video_url.startswith('data:video/mp4;base64,')
    assert len(result.screen_images) == 5
    with pytest.raises(ValueError):
        animation.normalize_video(b'not a movie')

def test_video_frames_are_screened_and_cache_does_not_regenerate(tmp_path, clip):
    editor = Editor(content=clip)
    editor.slot = lambda: MediaSlot(editor, 'to_video', {}, {})
    from tests.classroom.test_classroom import ALLOW
    conversation, _, judge = talk(tmp_path, editor, [ALLOW] * 6 + [CLEAN])
    first = conversation.animate('Raise trunk')
    assert first.ok and first.plan['kind'] == 'video'
    assert len(judge.prompts) == 7
    assert conversation.animate('Raise trunk').plan == first.plan
    assert len(editor.calls) == 1

def test_unsafe_generated_frame_is_not_published(tmp_path, clip):
    editor = Editor(content=clip)
    editor.slot = lambda: MediaSlot(editor, 'to_video', {}, {})
    from tests.classroom.test_classroom import ALLOW
    blocked = '{"verdict":"block","reason":"private","text_found":[]}'
    conversation, _, _ = talk(tmp_path, editor, [ALLOW, ALLOW, blocked, blocked])
    result = conversation.animate('Raise trunk')
    assert not result.ok and result.plan is None
    assert len(editor.calls) == 1

def test_latest_video_survives_store_reopen_and_is_scoped(tmp_path):
    path = tmp_path / 'portfolio.sqlite3'
    store = Portfolio(path)
    store.begin('course', 'colour', 'zh', '')
    for aid, did, video in [('one', 'drawing', 'first'), ('two', 'other', 'other'), ('three', 'drawing', 'latest')]:
        store.record('course', aid, 'painting-to-animation', [did], {'video_url': video})
    restored = Portfolio(path)
    assert restored.latest_video('course', 'drawing') == 'latest'
    assert restored.latest_video('another', 'drawing') is None
    assert restored.latest_video('course', 'missing') is None
    assert restored.course('course')['activities'][0]['summary']['kind'] == 'video'


def test_story_uses_saved_video_after_reopening_course(tmp_path):
    from studio.classroom.classroom import Classroom
    from tests.classroom.test_classroom import Scripted, CLASS, ALLOW, DRAWING, outputs_of
    from tests.classroom.test_classroom_integration import book
    client = Scripted([ALLOW, ALLOW])
    classroom = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": client, "vlm.director": client},
                          portfolio=Portfolio(tmp_path / "course.sqlite3"))
    try:
        sid = classroom.begin(CLASS)
        from pathlib import Path
        did = classroom.add_drawing(sid, Path(DRAWING).read_bytes())
        classroom.portfolio.record(sid, "saved-video", "painting-to-animation", [did],
                                   {"video_url": "data:video/mp4;base64,AAAA"})
        other = classroom.add_drawing(sid, Path(DRAWING).read_bytes())
        restored_sid = classroom.edit_course(sid)["session_id"]
        output = outputs_of(book(classroom, restored_sid, [did, other]))
        assert "video_url" not in output["pages"][1]
        assert output["pages"][0]["video_url"] == "data:video/mp4;base64,AAAA"
        aid = output["artifact_id"]
        assert classroom.portfolio.activity(sid, aid)["outputs"]["pages"] == output["pages"]
    finally:
        classroom.close()
