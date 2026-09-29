"""What the teacher's ledger view shows of NVIDIA's second look: its codes, and nothing else of it.

A screen's note became "<verdict> second-look:<what it said>" when the second reader was wired in, and
the ledger line's reason was still looked up by the whole note, so with the reader on every refused
drawing would have lost its reason on the teacher's page.
"""
from studio.core.ledger import Entry
from studio.server.stream import ledger_line


def line(note, gate="pass", skill="studio-safety"):
    return ledger_line(Entry(session="s", stage="screen", skill=skill, gate=gate, inputs_hash="h", note=note), "r")


def test_a_refused_drawing_keeps_its_reason_when_the_second_look_follows_the_verdict():
    assert line("block second-look:clear", gate="fail")["reason_code"] == "photo_not_drawing"
    assert line("unsafe second-look:sexual", gate="fail")["reason_code"] == "unsafe_image"
    assert line("empty", gate="fail")["reason_code"] == "blank_page"
    assert line("soften second-look:violence")["reason_code"] is None, "a drawing that went ahead has no refusal reason"


def test_the_second_looks_codes_reach_the_teachers_view():
    assert line("soften second-look:violence,weapons")["second_look"] == "violence,weapons"
    assert line("allow second-look:unavailable")["second_look"] == "unavailable"
    made = line("generated media safety fail second-look:sexual", gate="fail", skill="painting-to-animation")
    assert made["second_look"] == "sexual"
    assert line("allow")["second_look"] is None and line("")["second_look"] is None
