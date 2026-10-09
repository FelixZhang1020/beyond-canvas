"""What the record may say a child said.

Read out of one class (course 3f2328b0ef1e on the hosted Spark).
The teacher opened 聊聊你的画 before the studio had said anything — on that tab
the composer hid the button that opens the conversation, so typing was the only
thing the page offered — and sent the question she wanted put to the child. It
was written into the course as the CHILD's words, and the studio answered a
question with a question, having quietly written an opening nobody ever saw.

The class being taken over by a second window is the same afternoon's other
fault, fixed separately (SessionGone and the page's rejoin); its test lives in
tests/classroom/test_portfolio.py.
"""
from studio.classroom.portfolio import Portfolio
from test_classroom import room, png, CLASS, ALLOW, GOOD, GROUNDED, CLEAN, run  # noqa: F401


def test_a_child_turn_before_the_studio_has_opened_is_refused_and_written_nowhere(tmp_path, room, png):
    """The transcript column is a record of a child's words, and nothing else."""
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    course = classroom.begin(CLASS)
    drawing = classroom.add_drawing(course, png)

    events = run(classroom, course, drawing, {"transcript": "你猜猜这只帕丁顿熊准备在大雪天去做什么？"})

    stopped = [data for _, data in events if data.get("status") == "stopped"]
    assert stopped and stopped[0]["reason_code"] == "no_opening"
    # The refusal itself is recorded, as every refusal is, and the dialogue column
    # leaves status records out. What must not exist is the child's turn.
    saved = classroom.portfolio.course(course)["activities"]
    assert [a["skill"] for a in saved] == ["art-feedback"], "a teacher's question is not a child's answer"
    assert saved[0]["summary"]["status"] == "stopped" and saved[0]["summary"]["reason_code"] == "no_opening"
    assert not classroom.client.prompts, "no model is asked to answer a turn that never happened"


def test_the_childs_words_are_recorded_once_the_studio_has_opened(tmp_path, room, png):
    """The positive control: after an opening the same send is an ordinary reply."""
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN, GOOD, GROUNDED, CLEAN])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    course = classroom.begin(CLASS)
    drawing = classroom.add_drawing(course, png)

    run(classroom, course, drawing)
    run(classroom, course, drawing, {"transcript": "他要去上学。"})

    skills = [activity["skill"] for activity in classroom.portfolio.course(course)["activities"]]
    assert "confirmed-words" in skills


def test_a_course_whose_opening_was_never_saved_still_counts_as_opened(tmp_path, room, png):
    """Today's classes hold replies and no opening. Re-entering one must not refuse the next answer."""
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    course = classroom.begin(CLASS)
    drawing = classroom.add_drawing(course, png)
    classroom.portfolio.record(course, "reply", "art-feedback", [drawing],
                               {"beat": "reply", "text": "他准备去做什么呢？", "question": ""})
    classroom.end(course)

    session = classroom.edit_course(course)["session_id"]
    conversation = classroom._conversation(classroom.sessions[session], drawing)
    assert "他准备去做什么呢？" in conversation.opening
