import pytest

from studio.core.slots import UnknownSlot, load_profile, resolve

PROFILE = """
slots:
  vlm.director:
    provider: openrouter
    model: stepfun/step-3.7-flash
    options:
      reasoning_effort: low
      max_tokens: 1200
      provider_order: [StepFun]
  vlm.studio:
    provider: openrouter
    model: stepfun/step-3.7-flash
"""


@pytest.fixture
def profile_path(tmp_path):
    path = tmp_path / "test.yaml"
    path.write_text(PROFILE, encoding="utf-8")
    return path


def test_load_profile_reads_provider_model_and_options(profile_path):
    config = resolve("vlm.director", load_profile(profile_path))
    assert config.provider == "openrouter"
    assert config.model == "stepfun/step-3.7-flash"
    assert config.options["max_tokens"] == 1200
    assert config.options["provider_order"] == ["StepFun"]


def test_a_slot_without_options_gets_an_empty_dict(profile_path):
    assert resolve("vlm.studio", load_profile(profile_path)).options == {}


def test_unknown_slot_error_lists_the_slots_that_do_exist(profile_path):
    with pytest.raises(UnknownSlot) as caught:
        resolve("vlm.missing", load_profile(profile_path))
    assert "vlm.director" in str(caught.value)


def test_a_bare_name_resolves_against_the_bundled_profile_directory():
    assert "vlm.director" in load_profile("cloud")


# --- per-provider defaults ------------------------------------------------
#
# Added when StepFun First moved onto a subscription that answers on
# its own base URL. The eight StepFun slots that deployment runs are inherited
# from `api` and must stay inherited, so the address could not be written onto
# each slot without copying seven other things with it.

PARENT = """
slots:
  vlm.director:
    provider: stepfun
    model: step-3.7-flash
    options:
      max_tokens: 1200
  video.animation:
    provider: replicate
    model: wan-video/wan-2.2-i2v-a14b
"""

# An absolute `extends`, because a relative one resolves against the working
# directory rather than against the file doing the extending. No bundled profile
# writes one — they all use a bare name, which resolves inside the profiles dir —
# so that is a trap left standing, not one this test is about.
CHILD = """
extends: {parent}
provider_options:
  stepfun:
    base_url: https://example.test/plan/v1
slots:
  vlm.studio:
    provider: stepfun
    model: step-3.7-flash
"""


def family_at(tmp_path, parent=PARENT, extra=""):
    """A parent profile and a child that extends it, written side by side."""
    parent_path = tmp_path / "parent.yaml"
    parent_path.write_text(parent, encoding="utf-8")
    path = tmp_path / "child.yaml"
    path.write_text(CHILD.format(parent=parent_path) + extra, encoding="utf-8")
    return path


@pytest.fixture
def family(tmp_path):
    return family_at(tmp_path)


def test_a_provider_default_reaches_an_inherited_slot_without_rewriting_it(family):
    """The whole point: the slot stays in the parent, the address comes from here."""
    director = resolve("vlm.director", load_profile(family))
    assert director.options["base_url"] == "https://example.test/plan/v1"
    assert director.options["max_tokens"] == 1200


def test_a_provider_default_reaches_the_profile_s_own_slots_too(family):
    assert resolve("vlm.studio", load_profile(family)).options["base_url"] == "https://example.test/plan/v1"


def test_another_provider_s_slots_are_left_alone(family):
    """A StepFun address handed to Replicate would be nonsense it might not refuse."""
    assert "base_url" not in resolve("video.animation", load_profile(family)).options


def test_a_slot_that_names_its_own_value_keeps_it(tmp_path):
    slots = load_profile(family_at(tmp_path, extra="""    options:
      base_url: https://example.test/pinned/v1
"""))
    assert slots["vlm.studio"].options["base_url"] == "https://example.test/pinned/v1"
    assert slots["vlm.director"].options["base_url"] == "https://example.test/plan/v1"


def test_a_child_s_default_beats_its_parent_s(tmp_path):
    """Why slots and defaults are kept apart until the outermost call.

    Merged at each level, the parent's default would arrive at the child already
    looking like a slot option — and a slot option always wins, so the child
    could never overrule the profile it extends.
    """
    path = family_at(tmp_path, parent=PARENT + """
provider_options:
  stepfun:
    base_url: https://example.test/old/v1
    timeout_s: 30
""")
    director = resolve("vlm.director", load_profile(path))
    assert director.options["base_url"] == "https://example.test/plan/v1"
    # Untouched keys still come through, so a child overrides one value rather
    # than replacing the parent's whole block.
    assert director.options["timeout_s"] == 30


def test_a_profile_with_no_provider_options_is_unchanged(profile_path):
    assert resolve("vlm.studio", load_profile(profile_path)).options == {}


def test_two_profiles_that_extend_each_other_are_refused(tmp_path):
    """Covered by nothing until the loader was split in two and
    the visited set changed from one shared mutable set to a value passed down.
    Without this, a cycle would recurse until Python's stack gave out.
    """
    first, second = tmp_path / "first.yaml", tmp_path / "second.yaml"
    first.write_text(f"extends: {second}\nslots: {{}}\n", encoding="utf-8")
    second.write_text(f"extends: {first}\nslots: {{}}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cycle"):
        load_profile(first)


# --- where StepFun First makes its video -----------------------------------
#
# For a while one deployment name meant two boxes, chosen by
# BEYOND_CANVAS_MACHINE: from the Mac, the clip was bought from Replicate; on the
# Spark, which holds the 14B model, it was made there. The Mac + 4090 variant was
# archived and the switch went with it; the Spark is the only box.

def test_stepfun_first_makes_its_video_on_the_spark_and_keeps_the_subscription(monkeypatch):
    monkeypatch.setenv("BEYOND_CANVAS_MACHINE", "anything")  # read by nothing any more
    profile = load_profile("stepfun")
    video = resolve("video.animation", profile)
    assert (video.provider, video.model) == ("localvideo", "wan2.2-i2v-a14b")
    assert video.options["base_url"] == "http://127.0.0.1:7260"
    assert profile["tts.studio"].options["base_url"] == "https://api.stepfun.com/step_plan/v1"
