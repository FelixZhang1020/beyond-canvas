import pytest

from evalkit.rubric import run_rubric
from evalkit.rubric.assisted import rule_3_grounded_details, rule_4_non_presumptive, rule_12_followup
from studio.core.errors import ModelRefused

IMAGE = "data:image/png;base64,AAAA"
FEEDBACK = (
    "I notice your dog is purple and your sun has pointy triangle rays. "
    "I also see two people holding hands. "
    "What are they doing together?"
)


def test_two_grounded_details_pass_rule_3(fake_client):
    client = fake_client(['{"grounded": ["purple dog", "triangle rays", "two people"]}'])
    result = rule_3_grounded_details(FEEDBACK, IMAGE, client)
    assert result.status == "pass"
    assert "purple dog" in result.evidence


def test_one_grounded_detail_fails_rule_3(fake_client):
    client = fake_client(['{"grounded": ["purple dog"]}'])
    result = rule_3_grounded_details(FEEDBACK, IMAGE, client)
    assert result.status == "fail"
    assert "1" in result.evidence


def test_a_fenced_json_reply_is_still_parsed(fake_client):
    client = fake_client(['```json\n{"grounded": ["a", "b"]}\n```'])
    assert rule_3_grounded_details(FEEDBACK, IMAGE, client).status == "pass"


def test_repeated_malformed_json_is_refused(fake_client):
    client = fake_client(["not json at all", "still not json"])
    with pytest.raises(ModelRefused):
        rule_3_grounded_details(FEEDBACK, IMAGE, client)


def test_the_image_reaches_the_judge(fake_client):
    client = fake_client(['{"grounded": ["a", "b"]}'])
    rule_3_grounded_details(FEEDBACK, IMAGE, client)
    assert client.calls[0]["images"] == [IMAGE]


def test_a_judge_call_asks_for_its_own_large_token_budget(fake_client):
    """Measured: Step 3.7 Flash spent 3524 completion tokens to answer
    the presumption prompt with one line of JSON, and returned empty at the
    profile's 1600. A judge must not inherit the chat budget."""
    client = fake_client(['{"grounded": ["a", "b"]}', '{"presumptive": []}'])
    rule_3_grounded_details(FEEDBACK, IMAGE, client)
    rule_4_non_presumptive(FEEDBACK, IMAGE, client)
    assert client.calls[0]["max_tokens"] >= 4000
    assert client.calls[1]["max_tokens"] >= 4000


def test_no_presumptive_claims_passes_rule_4(fake_client):
    client = fake_client(['{"presumptive": []}'])
    assert rule_4_non_presumptive(FEEDBACK, IMAGE, client).status == "pass"


def test_a_presumptive_claim_fails_rule_4_and_is_quoted(fake_client):
    client = fake_client(['{"presumptive": ["calls the purple blob a mushroom"]}'])
    result = rule_4_non_presumptive(FEEDBACK, IMAGE, client)
    assert result.status == "fail"
    assert "mushroom" in result.evidence


DIALOGUE = "Companion: Where is the boat going?\nChild: To the house."


def test_a_later_question_is_judged_against_the_conversation(fake_client):
    client = fake_client(['{"question_issues": [], "why": "asks who waits at the house"}'])
    result = rule_12_followup("So the boat goes to the house. Who is waiting there?", DIALOGUE,
                              "The traveller is going to the house.", client)
    assert result.status == "pass"
    assert "Where is the boat going?" in client.calls[0]["prompt"]
    assert client.calls[0]["images"] == [], "a question is judged on the words, not the picture"


def test_a_question_the_child_already_answered_fails_and_is_quoted(fake_client):
    client = fake_client(['{"question_issues": ["asks again where the boat goes"]}'])
    result = rule_12_followup("Where is the boat going?", DIALOGUE, "It goes to the house.", client)
    assert result.status == "fail" and "again" in result.evidence


def test_a_judge_that_answers_with_a_string_is_read_as_one_item(fake_client):
    client = fake_client(['{"question_issues": "repeats the last question"}'])
    result = rule_12_followup("Where is the boat going?", DIALOGUE, "To the house.", client)
    assert result.status == "fail" and result.evidence == "repeats the last question"


def test_the_question_judge_lists_a_reason_the_child_never_gave(fake_client):
    """Live on the Spark: "is the sign there to remind the dog she is coming?"."""
    client = fake_client(['{"question_issues": []}'])
    rule_12_followup("What is the sign for?", "", "She brings the dog a bone every day.", client)
    assert "even as a guess the child could say" in client.calls[0]["prompt"]


def test_a_reply_with_no_question_is_not_asked_about(fake_client):
    client = fake_client(['{"presumptive": []}', '{"invented": []}'])
    report = run_rubric("So they walked all the way to their mum.", entrance="colour", image_data_uri=IMAGE,
                        client=client, child_said="they walked all the way to their mum",
                        dialogue_context=DIALOGUE)
    followup = next(result for result in report.results if result.rule == 12)
    assert followup.status == "skip" and "no question" in followup.evidence
    assert not any("question_issues" in call["prompt"] for call in client.calls)


def test_what_the_child_said_earlier_is_theirs_to_the_invention_judge(fake_client):
    client = fake_client(['{"presumptive": []}', '{"invented": []}', '{"question_issues": []}'])
    run_rubric("So the dog found the house. Who opens the door?", entrance="colour", image_data_uri=IMAGE,
               client=client, child_said="the dog found the house", dialogue_context=DIALOGUE,
               earlier_child_words="the purple one is my dog")
    invention = next(call["prompt"] for call in client.calls if '"invented"' in call["prompt"])
    naming = next(call["prompt"] for call in client.calls if '"presumptive"' in call["prompt"])
    assert "the purple one is my dog" in invention and "the dog found the house" in invention
    assert "the purple one is my dog" in naming


def test_run_rubric_without_an_image_skips_the_two_assisted_rules():
    report = run_rubric(FEEDBACK, entrance="colour")
    statuses = {result.rule: result.status for result in report.results}
    assert statuses[3] == "skip"
    assert statuses[4] == "skip"
    assert len(report.scored) == 9


def test_run_rubric_with_an_image_scores_every_reachable_rule(fake_client):
    client = fake_client(['{"grounded": ["purple dog", "triangle rays"]}', '{"presumptive": []}'])
    report = run_rubric(FEEDBACK, entrance="colour", image_data_uri=IMAGE, client=client)
    assert len(report.scored) == 11
    assert report.passed
    assert report.pass_rate == 1.0


def test_run_rubric_returns_every_rule_in_order():
    """Fourteen rules, no gaps. There is no rule 0 and none is silently dropped."""
    report = run_rubric(FEEDBACK, entrance="colour")
    assert [result.rule for result in report.results] == list(range(1, 15))


def test_a_dead_judge_skips_its_rule_instead_of_killing_the_run(fake_client):
    """A judge's token cost has a long tail. One unlucky call must not abort a
    benchmark, and must never be recorded as a pass."""
    client = fake_client(['{"grounded": ["a", "b"]}', "not json", "still not json"])
    report = run_rubric(FEEDBACK, entrance="colour", image_data_uri=IMAGE, client=client)
    statuses = {result.rule: result.status for result in report.results}
    assert statuses[3] == "pass"
    assert statuses[4] == "skip"
    assert len(report.scored) == 10
    assert report.passed


def test_a_skipped_judge_lowers_the_rules_scored_rather_than_the_score(fake_client):
    client = fake_client(['{"grounded": ["a", "b"]}', "not json", "still not json"])
    report = run_rubric(FEEDBACK, entrance="colour", image_data_uri=IMAGE, client=client)
    assert report.pass_rate == 1.0
    assert len(report.scored) < 11


def test_a_reply_is_not_asked_to_ask_a_question(fake_client):
    """Rule 12 grades the opening. The spec tells beat four to stop talking, so
    scoring a reply down for not asking would penalise getting out of the way.
    Found by a live run."""
    reply = "So you drew the road that long because they walked a long way."
    client = fake_client(['{"grounded": ["a", "b"]}', '{"presumptive": []}', '{"invented": []}'])
    report = run_rubric(
        reply, entrance="colour", image_data_uri=IMAGE, client=client,
        child_said="they walked a long way",
    )
    statuses = {result.rule: result.status for result in report.results}
    assert statuses[2] == "skip"
    assert statuses[9] == "skip"
    assert statuses[12] == "skip"
    assert statuses[13] == "pass"


def test_an_opening_is_still_asked_to_ask_a_question():
    """The skip must not leak into the case rule 12 exists for."""
    report = run_rubric("I see orange lines and three green dots.", entrance="colour")
    statuses = {result.rule: result.status for result in report.results}
    assert statuses[12] == "fail"


def test_a_failing_rule_shows_up_in_failures():
    report = run_rubric("Your painting is beautiful! You're so talented.", entrance="colour")
    failed = {result.rule for result in report.failures}
    assert {1, 2, 9} <= failed


def test_rule_4_is_told_what_the_child_said(fake_client):
    """Section 5a: repeating a name the child gave is not presuming it."""
    client = fake_client(['{"presumptive": []}'])
    rule_4_non_presumptive("Your grandma's tree.", "data:,x", client, child_said="grandma's tree")
    assert "grandma's tree" in client.calls[0]["prompt"]
    assert "THEIRS" in client.calls[0]["prompt"]


def test_rule_4_says_nothing_about_a_child_who_said_nothing(fake_client):
    client = fake_client(['{"presumptive": []}'])
    rule_4_non_presumptive("A purple oval.", "data:,x", client)
    assert "The child has already said" not in client.calls[0]["prompt"]


KITES = "flying kites in the square, with marker outlines"


def test_rule_4_is_told_what_the_class_was_drawing(fake_client):
    """Seen live: a class whose teacher wrote that it drew kites had its
    opening refused on this rule three times, twice for calling the red winged shape a
    kite. The judge had never been shown the teacher's line, so the lesson's own subject
    read as a guess, and the teacher was shown the gate message instead of an opening."""
    client = fake_client(['{"presumptive": []}'])
    rule_4_non_presumptive("I see a big red kite.", "data:,x", client, lesson_intent=KITES)
    prompt = client.calls[0]["prompt"]
    assert KITES in prompt
    assert "what the class was drawing" in prompt


def test_the_lesson_never_licenses_a_shape_the_drawing_shows_as_something_else(fake_client):
    """A child in a kite class may draw a finished bird with a beak and feet and no
    string. Pointing at one feature a kite could have is not enough to call it one."""
    client = fake_client(['{"presumptive": []}'])
    rule_4_non_presumptive("I see your kite.", "data:,x", client, lesson_intent=KITES)
    assert "plainly shows it as something else" in client.calls[0]["prompt"]


def test_what_the_child_said_outranks_what_the_class_was_drawing(fake_client):
    """Review: with both clauses and no order between them, a reply that
    said "bird" back to a child in a kite class could be refused, and one that called
    the child's bird a kite could pass because the lesson named it."""
    client = fake_client(['{"presumptive": []}'])
    rule_4_non_presumptive("Your bird is going home.", "data:,x", client,
                           child_said="it's a bird going home", lesson_intent=KITES)
    prompt = client.calls[0]["prompt"]
    assert "outranks the teacher's line" in prompt
    # The order names "the teacher's line" and gives the child the last word, so it follows both.
    assert prompt.index("outranks") > prompt.index("what the class was drawing")
    assert prompt.index("outranks") > prompt.index("The child has already said")


@pytest.mark.parametrize("said, lesson", [("it's a bird", ""), ("", KITES)])
def test_the_order_is_only_given_when_both_have_spoken(fake_client, said, lesson):
    client = fake_client(['{"presumptive": []}'])
    rule_4_non_presumptive("A red shape.", "data:,x", client, child_said=said, lesson_intent=lesson)
    assert "outranks the teacher's line" not in client.calls[0]["prompt"]


def test_rule_4_says_nothing_about_a_lesson_nobody_typed(fake_client):
    client = fake_client(['{"presumptive": []}'])
    rule_4_non_presumptive("A purple oval.", "data:,x", client, lesson_intent="   ")
    assert "what the class was drawing" not in client.calls[0]["prompt"]


@pytest.mark.parametrize("child_said", ["", "the kite is going to the moon"])
def test_the_rubric_hands_the_lesson_line_to_rule_4(child_said):
    """On the opening and on the reply alike: a reply may say "kite" back too."""
    seen = []

    class Routing:
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            from studio.providers.base import ChatResult

            if "real-world IDENTITY" in prompt:
                seen.append(prompt)
            reply = '{"grounded": ["a", "b"], "presumptive": [], "connected": true, "invented": []}'
            return ChatResult(reply, 1, 1, 0, 0.0, 0.0, "fake", "fake")

    run_rubric("I see a big red kite. Where is it flying?", entrance="colour", image_data_uri=IMAGE,
               client=Routing(), child_said=child_said, lesson_intent=KITES)
    assert seen and all(KITES in prompt for prompt in seen)
