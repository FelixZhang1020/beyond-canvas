"""A media slot is called by what it does; the profile holds the vendor's words.

These tests exist because the operator expects to swap these models when the
pictures or the voice are not good enough. The property being protected is that
such a swap is an edit to a profile and not to any Python.
"""

import pytest

from studio.core.errors import UnknownTask
from studio.providers import build_media_slot
from studio.providers.media import MediaResult, MediaSlot
from studio.core.slots import SlotConfig


class Recorder:
    """A media client that records the body it was handed and returns nothing."""

    def __init__(self):
        self.body = None

    def make(self, inputs):
        self.body = inputs
        return MediaResult(urls=[], payload={}, provider="recorder", model="recorder")


def slot(task, fields=None, extra=None):
    recorder = Recorder()
    return recorder, MediaSlot(recorder, task, dict(fields or {}), dict(extra or {}))


def config(slot_name, options):
    return SlotConfig(slot=slot_name, provider="replicate", model="a/b", options=options)


def test_speak_is_translated_into_the_vendors_field_names():
    recorder, voice = slot("speak", {"text": "tts_text", "voice": "source_audio"})
    voice.speak("你好", voice="https://example.test/child.wav")
    assert recorder.body == {"tts_text": "你好", "source_audio": "https://example.test/child.wav"}


def test_constants_from_the_profile_ride_along_on_every_call():
    """CosyVoice needs a mode on every call, and no skill should have to know that."""
    recorder, voice = slot(
        "speak",
        {"text": "tts_text"},
        {"task": "Instructed Voice Generation", "instruction": "用温柔的语气"},
    )
    voice.speak("你好")
    assert recorder.body["task"] == "Instructed Voice Generation"
    assert recorder.body["instruction"] == "用温柔的语气"
    assert recorder.body["tts_text"] == "你好"


def test_an_argument_not_given_is_left_out_rather_than_sent_as_null():
    recorder, voice = slot("speak", {"text": "tts_text", "voice": "source_audio"})
    voice.speak("你好")
    assert "source_audio" not in recorder.body


def test_an_unmapped_argument_keeps_its_canonical_name():
    recorder, editor = slot("edit_image", {"instruction": "prompt"})
    editor.edit_image("data:image/png;base64,xx", "make it a storybook page")
    assert recorder.body == {"image": "data:image/png;base64,xx", "prompt": "make it a storybook page"}


def test_swapping_the_model_is_a_change_of_mapping_and_nothing_else():
    """The whole point: same call, different vendor, no code touched.

    A skill that said `prompt=` would have to be rewritten when the voice model
    changed. A skill that says `speak(text=...)` does not.
    """
    first, one = slot("speak", {"text": "tts_text"}, {"task": "zero-shot voice clone"})
    second, two = slot("speak", {"text": "text"}, {"voice_id": "warm-01"})

    one.speak("今天画了什么？")
    two.speak("今天画了什么？")

    assert first.body == {"tts_text": "今天画了什么？", "task": "zero-shot voice clone"}
    assert second.body == {"text": "今天画了什么？", "voice_id": "warm-01"}


def test_asking_a_slot_for_a_job_it_does_not_do_names_the_job_it_does():
    _, voice = slot("speak", {"text": "tts_text"})
    with pytest.raises(UnknownTask) as caught:
        voice.to_mesh("data:image/png;base64,xx")
    assert "'speak'" in str(caught.value)


def test_a_profile_with_no_task_is_refused_at_build_time():
    with pytest.raises(UnknownTask) as caught:
        build_media_slot(config("tts.studio", {"fields": {"text": "tts_text"}}))
    assert "must name one of" in str(caught.value)


def test_a_profile_that_maps_a_field_the_task_does_not_have_is_refused():
    """A typo in a profile must not wait for a child to be standing there."""
    with pytest.raises(UnknownTask) as caught:
        build_media_slot(config("tts.studio", {"task": "speak", "fields": {"promt": "x"}}))
    assert "promt" in str(caught.value)
    assert "'text'" in str(caught.value)


def test_every_media_slot_in_the_cloud_profile_builds():
    """The profile is only useful if it actually resolves. No key needed to check.

    `build_media_slot` validates the task and the field map before it ever
    reaches the client, so this catches a bad mapping without a network call —
    but the client construction does need a key, so this asserts the validation
    rather than the whole build.
    """
    from studio.providers.media import TASKS
    from studio.core.slots import load_profile

    media = {
        name: entry for name, entry in load_profile("cloud").items()
        if entry.provider in ("replicate", "fal")
    }
    assert media, "the cloud profile should carry media slots"
    for name, entry in media.items():
        task = entry.options.get("task")
        assert task in TASKS, f"{name} declares task {task!r}"
        unknown = set(entry.options.get("fields") or {}) - set(TASKS[task])
        assert not unknown, f"{name} maps {unknown}, which {task} does not take"


@pytest.mark.parametrize('bad', ['image', ['images'], [2], {'image': True}])
def test_array_mapping_rejects_noncanonical_argument_names(bad):
    with pytest.raises(UnknownTask, match='array_fields'):
        build_media_slot(config('image.edit', {'task': 'edit_image', 'array_fields': bad}))
