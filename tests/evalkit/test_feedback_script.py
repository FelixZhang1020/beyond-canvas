"""The feedback script serves two entrances the teacher picks by hand.

Section 5a of the spec: on the colour entrance the child tells the story inside
their picture and nothing is corrected; on the sketch entrance a plaster-cast
study gets a professional read of light, proportion and structure, and a
correction arrives as something to try. Age is not a parameter on either.
"""

from pathlib import Path

import pytest
from conftest import load_script

SCRIPT = Path("skills/art-feedback/scripts/feedback.py")
DRAWING = "skills/art-feedback/evals/files/scribble.png"


@pytest.fixture(scope="module")
def module():
    return load_script(SCRIPT, "feedback_script")


@pytest.fixture
def colour(module):
    return module.ClassSettings(entrance="colour", language="en")


@pytest.fixture
def sketch(module):
    return module.ClassSettings(entrance="sketch", language="en")


def squeezed(text):
    """Whitespace-normalised, because prompts wrap where they read well."""
    return " ".join(text.split())


def test_the_entrance_is_chosen_by_hand_and_must_be_one_of_two(module):
    """Section 5a: no automatic detection, no default, and no third kind of class."""
    with pytest.raises(ValueError):
        module.ClassSettings(entrance="crayon", language="en")
    with pytest.raises(TypeError):
        module.ClassSettings(language="en")


def test_the_prompt_states_the_language(module):
    assert "Chinese" in module.build_prompt(module.ClassSettings("colour", "zh"))
    assert "English" in module.build_prompt(module.ClassSettings("colour", "en"))
    assert "Chinese" in module.build_prompt(module.ClassSettings("sketch", "zh"))


@pytest.mark.parametrize("entrance", ["colour", "sketch"])
def test_a_chinese_class_is_told_its_opening_words_in_chinese(module, entrance):
    """Measured: told only "I see" or "I notice", 14 of 90 Chinese openings began
    in English, 12 of them under a subject-first lesson line. Naming the Chinese openers took
    it to 0 of 90. They have to be words rule 2 accepts, or the prompt and its grader drift."""
    from evalkit.rubric.lexicons import OBSERVATION_OPENERS

    prompt = module.build_prompt(module.ClassSettings(entrance, "zh"))
    named = [opener for opener in OBSERVATION_OPENERS["zh"] if opener in prompt]
    assert len(named) >= 2, f"the {entrance} prompt names {named} of rule 2's Chinese openers"


def test_neither_prompt_grades_by_age(module, colour, sketch):
    for settings in (colour, sketch):
        prompt = module.build_prompt(settings)
        for band in ("3-5", "6-8", "9-12", "aged"):
            assert band not in prompt


def test_the_colour_prompt_corrects_nothing_and_hands_the_picture_to_the_child(module, colour):
    """Operator: an opening that guessed where the ship was going was "very subjective"; the child says
    what they drew first, and the replies, which keep the world question, build on it."""
    prompt = module.build_prompt(colour)
    assert "Correct nothing" in prompt
    assert "Hand the picture to the child" in prompt and "Say what you see, not what it means" in prompt
    for forbidden in ("talented", "beautiful", "should"):
        assert forbidden in prompt


def test_the_sketch_prompt_reads_light_proportion_and_structure(module, sketch):
    """Professional critique, and the correction arrives as something to try."""
    prompt = squeezed(module.build_prompt(sketch))
    for dimension in ("light", "proportion", "structure"):
        assert dimension in prompt
    assert "something to try" in prompt
    assert "Correct nothing" not in prompt


def test_the_sketch_prompt_asks_about_the_process_not_a_story(module, sketch):
    """A plaster cast has no story. The spec's sketch question is about the process."""
    prompt = squeezed(module.build_prompt(sketch))
    assert "changed the most" in prompt
    assert "WORLD inside the picture" not in prompt
    assert "not a character" in prompt


def test_both_prompts_forbid_repeating_a_name_found_in_the_drawing(module, colour, sketch):
    for settings in (colour, sketch):
        assert "name" in module.build_prompt(settings).lower()


def test_write_feedback_sends_the_drawing_and_returns_the_reply(module, fake_client, colour):
    client = fake_client(["I notice orange loops. What did your hand do?"])
    text = module.write_feedback(DRAWING, colour, client)
    assert text == "I notice orange loops. What did your hand do?"
    assert client.calls[0]["images"][0].startswith("data:image/png;base64,")
    assert "I see" in client.calls[0]["prompt"]


def test_the_reply_prompt_carries_the_childs_words_and_the_opening(module, colour):
    prompt = module.build_reply_prompt(
        colour, "I see orange lines. What is happening?", "the wind blew the beans away",
        ("Companion: Where did the beans go?", "Child: They went into the garden."),
    )
    assert "the wind blew the beans away" in prompt
    assert "I see orange lines" in prompt
    assert "English" in prompt
    assert "Where did the beans go?" in prompt
    assert "They went into the garden." in prompt
    assert "never repeat an earlier question" in prompt


def test_the_colour_reply_asks_openly_and_keeps_its_guesses_to_itself(module, colour):
    """Live on the Spark: three replies in a row ended in a yes-or-no guess at a motive,
    and one turned the child's "little owner" into "you"."""
    prompt = module.build_reply_prompt(colour, "I see a dog.", "the dog waits for its little owner")
    assert "make it an open question" in prompt
    assert "Never a question they can answer with yes or no" in prompt
    assert "said as a statement, not asked" in prompt
    assert '"the little owner" stays the little owner, never "you"' in prompt


def test_the_colour_reply_is_told_the_question_it_answers_and_keeps_who_it_is_about(module, colour):
    """The castle class: asked why the soldier on the tower blew his trumpet, a child answered "to buy
    time", and four replies in eight on the Spark gave it to the mouse king or to "you"."""
    history = ("Companion: I see mice marching.\nWhat do they want?", "Child: The mouse king leads them.",
               "Companion: The soldier sees them.\nWhy is the soldier on the tower blowing his trumpet?")
    prompt = squeezed(module.build_reply_prompt(colour, "I see mice marching. What do they want?",
                                                "to buy time", history))
    assert 'The question they are answering: """Why is the soldier on the tower blowing his trumpet?"""' in prompt
    assert "it is about the one that question asked about" in prompt
    assert 'never to "you" (你) unless they said "I" (我)' in prompt
    first = squeezed(module.build_reply_prompt(colour, "I see a dog. Where is it going?", "to the park"))
    assert 'The question they are answering: """Where is it going?"""' in first, "the first answer answers the opening"


def test_a_closed_question_is_asked_for_again_alone_and_without_the_picture(module, fake_client, colour):
    client = fake_client(["Where is the dog going?"])
    asked = module.open_the_question("The dog ran away. Is it going home?", colour, client, "closed yes or no")
    assert asked == "Where is the dog going?"
    assert client.calls[0]["images"] == []
    assert "Is it going home?" in client.calls[0]["prompt"] and "closed yes or no" in client.calls[0]["prompt"]


def test_the_colour_reply_may_end_without_a_question(module, colour):
    """Section 5a: one question at most, and none at all once the child has said something whole."""
    prompt = module.build_reply_prompt(colour, "I see a road.", "they walked a long way")
    assert "none at all is fine" in prompt
    assert "Never offer two ready-made answers" in prompt


def test_the_colour_questions_ask_for_the_childs_story_not_a_small_fact(module, colour):
    """Operator: the questions were "very stupid"; they asked what kind of snow, not what happens."""
    reply = module.build_reply_prompt(colour, "I see a ship.", "it is going to the South Pole")
    assert "whole story of their picture" in reply and "first part still missing" in reply
    assert "never a small fact" in reply


def test_the_colour_reply_forbids_inventing_and_correcting(module, colour):
    """Rules 13 and 14 restated as instructions, beside the rules they mirror."""
    prompt = module.build_reply_prompt(colour, "opening", "the sun is angry")
    assert "OWN words" in prompt
    assert "no story of your own" in prompt.lower()
    assert "never correct" in prompt.lower()


def test_the_sketch_reply_builds_the_read_around_what_was_hard(module, sketch):
    """Section 5a: the technical read is built around what the child found hard."""
    prompt = squeezed(module.build_reply_prompt(
        sketch, "Which part did you change the most?", "the shadow, I kept making it too dark"
    ))
    assert "OWN words" in prompt
    assert "found hard" in prompt
    assert "something to try" in prompt
    assert "no story of your own" not in prompt.lower()


def test_write_reply_sends_the_drawing_and_returns_the_reply(module, fake_client, colour):
    client = fake_client(["So the wind blew the beans away?"])
    text = module.write_reply(
        DRAWING, colour, "I see orange lines. What is happening?", "the wind blew the beans away", client
    )
    assert text == "So the wind blew the beans away?"
    assert client.calls[0]["images"][0].startswith("data:image/png;base64,")
    assert "wind blew the beans" in client.calls[0]["prompt"]


def test_rung_two_offers_two_choices_and_never_repeats(module, colour):
    """A child who cannot invent can still choose, and choosing starts them talking."""
    prompt = module.build_rung_prompt(colour, 2, "What is happening here?")
    assert "two choices" in prompt
    assert "What is happening here?" in prompt
    assert "Never repeat" in prompt


def test_rung_three_speaks_as_a_character_in_the_drawing(module, colour):
    """A four-year-old cannot tell a story on request, but can answer a bird."""
    prompt = module.build_rung_prompt(colour, 3, "What is happening here?")
    assert "first person" in prompt
    assert "characters in the drawing" in prompt


def test_a_smaller_question_is_told_the_story_so_far(module, colour):
    """A child can fall quiet halfway: the smaller door must not forget what they said."""
    prompt = module.build_rung_prompt(colour, 2, "What is happening here?",
                                      ("Child: the purple one is my dog",))
    assert "the purple one is my dog" in prompt
    assert "child's names" in prompt


def test_the_sketch_rungs_stay_with_the_process(module, sketch):
    """Asking a plaster sphere where it is going would be absurd."""
    two = squeezed(module.build_rung_prompt(sketch, 2, "Which part did you change the most?"))
    assert "two choices" in two
    assert "the outline or the shading" in two
    assert "arriving" not in two
    three = squeezed(module.build_rung_prompt(sketch, 3, "Which part did you change the most?"))
    assert "first person" in three
    assert "object the student drew" in three


def test_there_is_no_rung_one_to_climb(module, colour):
    """Rung one is the opening question, already asked. Climbing means going smaller."""
    with pytest.raises(ValueError):
        module.climb_a_rung("x.png", colour, "asked", 1, None)


def test_climbing_sends_the_drawing_and_returns_the_smaller_question(module, fake_client, colour):
    client = fake_client(["Is he just arriving, or about to leave?"])
    text = module.climb_a_rung(DRAWING, colour, "What is happening here?", 2, client)
    assert text == "Is he just arriving, or about to leave?"
    assert client.calls[0]["images"][0].startswith("data:image/png;base64,")


def test_the_lesson_intent_reaches_the_opening_prompt_on_both_entrances(module):
    for entrance in ("colour", "sketch"):
        settings = module.ClassSettings(entrance, "en", lesson_intent="warm and cool colours side by side")
        prompt = module.build_prompt(settings)
        assert "warm and cool colours side by side" in prompt
        assert "do not force the connection" in prompt.lower()


def test_no_lesson_intent_leaves_the_prompt_unchanged(module, colour):
    """Most teachers will type nothing, and the prompt must not carry an empty clause."""
    assert "This class was working on" not in module.build_prompt(colour)


def test_both_colour_rungs_forbid_guessing_what_an_ambiguous_shape_is(module, colour):
    """Live run: rung 2 called the orange lines a snail and rung 3 called
    them a tree. The spec's own worked example ends 'the machine never once guessed
    what the lines were'."""
    for rung in (2, 3):
        prompt = squeezed(module.build_rung_prompt(colour, rung, "What is happening?"))
        assert "ambiguous shape" in prompt
        assert "meaning did not come across" in prompt


def test_the_command_line_requires_an_entrance(module):
    """The teacher picks. A run that names no entrance does not start."""
    with pytest.raises(SystemExit):
        module.build_parser().parse_args(["drawing.png"])
    arguments = module.build_parser().parse_args(["drawing.png", "--entrance", "sketch"])
    assert arguments.entrance == "sketch"
    assert not hasattr(arguments, "age")


def test_there_is_no_suggestion_switch(module):
    """Section 5a: the entrance fork replaced the teacher's switch, and both are deleted.
    A suggestion is what the sketch entrance gives as something to try; on colour
    there is none to switch on."""
    assert not hasattr(module, "SUGGESTION_CLAUSE")
    assert "suggest" not in " ".join(module.build_prompt(module.ClassSettings("colour", "en")).split()).lower()


def test_the_sketch_prompt_states_every_rule_it_is_graded_against(module, sketch):
    """A live run failed rule 2 on six of seven sketch drawings and
    rule 4 on two, because this prompt described the behaviour without naming it.
    Rules 6 and 7 are skipped on this entrance; the rest still apply, so the
    prompt has to ask for them."""
    prompt = squeezed(module.build_prompt(sketch))
    assert '"I see" or "I notice"' in prompt          # rule 2
    assert "Never assert what an ambiguous shape is" in prompt  # rule 4
    assert "under twenty words" in prompt             # rule 10
    assert "answered yes or no" in prompt             # rule 9


def test_the_two_openings_ask_for_the_same_opener(module, colour, sketch):
    """Rule 2 grades both entrances, so both prompts have to request it."""
    for settings in (colour, sketch):
        assert '"I see" or "I notice"' in squeezed(module.build_prompt(settings))


def test_the_sketch_prompt_caps_the_number_of_sentences_as_well_as_their_length(module, sketch):
    """Telling the model to split its sentences fixed rule 10 and produced a
    ten-sentence reply, which nothing grades: rule 10 measures length, not count.
    Seen in a live run."""
    prompt = squeezed(module.build_prompt(sketch))
    assert "no more than four" in prompt
    assert "leave it out" in prompt
