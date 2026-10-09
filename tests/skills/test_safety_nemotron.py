"""NVIDIA's safety model beside the four-verdict check: reading its answer, and the studio's rule.

No model runs here. What the weights really say about a monster is measured on the Spark and kept
in docs/measured/; these tests hold the part that must never drift: only sexual content stops a
child's drawing at the door, any flag refuses a machine-made picture on the way out, a teacher's
note is a code and never the model's words, and an answer that cannot be read is refused.
"""

from pathlib import Path

import pytest
from conftest import load_script

from studio.core.errors import ModelRefused

SCRIPT = Path("skills/studio-safety/scripts/nemotron.py")
POLICY = Path("skills/studio-safety/references/childrens-studio-policy.md")

TAXONOMY = ("Violence", "Sexual", "Criminal Planning/Confessions", "Guns and Illegal Weapons",
            "Controlled/Regulated Substances", "Suicide and Self Harm", "Sexual (minor)", "Hate/Identity Hate",
            "PII/Privacy", "Harassment", "Threat", "Profanity", "Needs Caution", "Other", "Manipulation",
            "Fraud/Deception", "Malware", "High Risk Gov Decision Making", "Political/Misinformation/Conspiracy",
            "Copyright/Trademark/Plagiarism", "Unauthorized Advice", "Illegal Activity", "Immoral/Unethical")


@pytest.fixture(scope="module")
def module():
    return load_script(SCRIPT, "nemotron_script")


def test_a_safe_answer_lets_the_drawing_in_with_nothing_for_the_teacher(module):
    ruling = module.at_the_door(module.read_answer("User Safety: safe"))
    assert ruling.proceeds and not ruling.soften and ruling.teacher_codes == ()


def test_a_monster_flagged_as_violence_comes_in_and_is_answered_warmly(module):
    """The case that matters most: a child who draws a monster is never refused for it."""
    ruling = module.at_the_door(module.read_answer("User Safety: unsafe\nSafety Categories: Violence, Threat"))
    assert ruling.proceeds and ruling.soften
    assert ruling.teacher_codes == ("violence", "threat")


@pytest.mark.parametrize("category", TAXONOMY)
def test_only_sexual_content_stops_a_drawing_at_the_door(module, category):
    ruling = module.at_the_door(module.read_answer(f"User Safety: unsafe\nSafety Categories: {category}"))
    assert ruling.proceeds == (not category.startswith("Sexual"))


def test_sexual_content_beside_another_flag_still_stops(module):
    ruling = module.at_the_door(module.read_answer("User Safety: unsafe\nSafety Categories: Violence, Sexual"))
    assert not ruling.proceeds and ruling.reason_code == "nemotron_sexual"


def test_a_flag_with_no_category_does_not_stop_a_child(module):
    """When the model is unsure what it saw, the drawing comes in; the four-verdict check still runs."""
    ruling = module.at_the_door(module.read_answer("User Safety: unsafe"))
    assert ruling.proceeds and ruling.soften and ruling.teacher_codes == ("unspecified",)


@pytest.mark.parametrize("category", TAXONOMY)
def test_any_flag_refuses_a_machine_made_picture(module, category):
    """A refused machine-made picture costs one retry; a harmful one shown to a child costs more."""
    ruling = module.on_the_way_out(module.read_answer(f"User Safety: unsafe\nSafety Categories: {category}"))
    assert not ruling.proceeds and ruling.reason_code == "nemotron_flagged"


def test_a_safe_machine_made_picture_goes_out(module):
    assert module.on_the_way_out(module.read_answer("User Safety: safe\nResponse Safety: safe")).proceeds


def test_a_flag_with_no_category_still_refuses_a_machine_made_picture(module):
    assert not module.on_the_way_out(module.read_answer("User Safety: unsafe")).proceeds


def test_thinking_out_loud_is_not_the_answer(module):
    """With a custom policy the model reasons first, and its reasoning quotes the answer format."""
    reply = ("<think>\nWe need to output:\nUser Safety: unsafe\nSafety Categories: Violence\n"
             "But a drawn monster is allowed by the policy.\n</think>User Safety: safe")
    reading = module.read_answer(reply)
    assert not reading.unsafe and reading.categories == ()


def test_an_answer_with_no_verdict_is_refused_rather_than_allowed(module):
    for reply in ("", "I cannot help with that.", "<think>User Safety: safe", "Safety Categories: Violence"):
        with pytest.raises(ModelRefused):
            module.read_answer(reply)
    # The refusal becomes a ledger note and reaches the page: a code, never the model's words about the child.
    with pytest.raises(ModelRefused) as refused:
        module.read_answer("The girl called Mei Lin looks frightened in this drawing.")
    assert "mei lin" not in str(refused.value).lower()


def test_a_teachers_note_is_a_code_and_never_the_models_words(module):
    """The ledger rule from an earlier review: no model prose about a child is ever kept."""
    reply = "User Safety: unsafe\nSafety Categories: the child seems frightened of someone at home, Violence"
    ruling = module.at_the_door(module.read_answer(reply))
    assert ruling.teacher_codes == ("other", "violence")
    assert set(ruling.teacher_codes) <= set(module.CODES.values()) | {"unspecified"}


def test_every_category_the_model_can_name_has_a_code(module):
    assert set(module.CODES) == {name.lower() for name in TAXONOMY}


def test_the_policy_lets_a_child_draw_what_children_draw(module):
    policy = module.inference_policy()
    allowed = policy.split("Allowed Behaviors:")[1]
    for subject in ("monster", "war", "crying", "blood", "weapon"):
        assert subject in allowed.lower(), subject
    assert "### Policy" in policy and "Disallowed Behaviors:" in policy
    assert "photograph" not in policy.split("Allowed Behaviors:")[0].lower(), \
        "a photo is the four-verdict check's job; disallowing it here would refuse the studio's own pictures"
    assert "741741" not in POLICY.read_text() and "988" not in POLICY.read_text(), "no US crisis line in a Chinese classroom"


def test_nothing_a_child_draws_is_named_in_the_list_of_what_is_not_allowed(module):
    """Measured on the Spark: with "realistic gore, real injury, real dead bodies" in the
    disallowed list, the 4B model flagged a stick-figure sword fight, a hunt and a bleeding friend as
    unsafe, all three of which NVIDIA's stock rules had called safe, and said the policy bans weapons,
    which it never did. A small model matches words. So the dark words live only in the allowed list."""
    disallowed = module.inference_policy().split("Disallowed Behaviors:")[1].split("Allowed Behaviors:")[0].lower()
    for word in ("gore", "blood", "injur", "wound", "dead", "death", "weapon", "gun", "sword", "fight", "violen", "monster"):
        assert word not in disallowed, f"{word!r} in the disallowed list turns a child's drawing of it unsafe"


def test_the_policy_the_model_reads_is_the_one_people_read(module):
    """One canonical place: the inference text is cut out of the Markdown policy, never retyped."""
    assert module.inference_policy() in POLICY.read_text()
