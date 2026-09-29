"""The ledger survives whatever a model can put into a note.

A note is bounded free text from a gate, and some of those gates quote a
model. Two characters a model can emit used to break the file: a Unicode
line separator, which `str.splitlines()` treats as a line end although JSON
does not, so one such note split the file and every later read of it failed;
and an unpaired surrogate, which `json.loads` accepts and a UTF-8 file
refuses, so the write raised and the decision was never recorded.
"""
from studio.core.ledger import Entry, Ledger


def line(note: str) -> Entry:
    return Entry(session="s", stage="scene-description", skill="scene-description", gate="fail",
                 inputs_hash="h", note=note)


def test_a_unicode_line_separator_inside_a_note_does_not_split_the_line(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(line("candidate adds a third elephant"))
    ledger.append(line("second"))
    assert [entry.note for entry in ledger.entries()] == ["candidate adds a third elephant", "second"]
    assert ledger.forget("s") == 2


def test_an_unpaired_surrogate_in_a_note_is_written_readably_rather_than_raising(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(line("\ud83d bad"))
    (entry,) = ledger.entries()
    assert "bad" in entry.note and "\ud83d" not in entry.note
