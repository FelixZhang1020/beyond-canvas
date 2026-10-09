"""The prompt page in system management shows every instruction a model is given.

Its promise is completeness, and a page that quietly misses one looks exactly as
complete as one that does not. So these fail the moment a prompt file or a named
prompt line exists that the book does not list, and the moment an entry points at
wording that is no longer there.
"""

import importlib
import json
import re
from pathlib import Path

from studio.core import prompt_book

ROOT = prompt_book.ROOT
BOOK = json.loads(prompt_book.BOOK.read_text(encoding="utf-8"))
ENTRIES = [entry for group in BOOK["groups"] for entry in group["entries"]]
PROMPT_FOLDERS = ("skills/*/assets/prompts/*.txt", "studio/prompts/*.txt", "studio/showpiece/prompts/*.txt")
# Developer tools, not the classroom or the showpiece: left off the page on purpose.
NOT_THE_PRODUCT = {"studio/ops/dayzero.py", "studio/ops/voice_lab.py"}
PROMPT_NAME = re.compile(r"PROMPT|SYSTEM|CLAUSE|QUESTION|INSTRUCTION")


def product_modules():
    studio = [p for p in (ROOT / "studio").rglob("*.py") if str(p.relative_to(ROOT)) not in NOT_THE_PRODUCT]
    return studio + sorted((ROOT / "skills").glob("*/scripts/*.py")) + sorted((ROOT / "evalkit/rubric").glob("*.py"))


def listed_lines():
    return {(entry["code"], part.split(".")[0]) for entry in ENTRIES if "code" in entry
            for part in entry["parts"] if not part.startswith("{")}


def test_every_prompt_file_is_on_the_page():
    files = {str(p.relative_to(ROOT)) for folder in PROMPT_FOLDERS for p in ROOT.glob(folder)}
    listed = {entry["file"] for entry in ENTRIES if "file" in entry}
    assert files, "the prompt folders moved; this test is looking in the wrong place"
    assert files - listed == set(), "add these to studio/core/prompt_book.json"


def test_every_named_prompt_line_in_the_product_is_on_the_page():
    unlisted = []
    for path in product_modules():
        for name, value in prompt_book.constants(path).items():
            text = isinstance(value, str) or (isinstance(value, dict) and value
                                              and all(isinstance(v, str) for v in value.values()))
            if text and PROMPT_NAME.search(name) and (str(path.relative_to(ROOT)), name) not in listed_lines():
                unlisted.append(f"{path.relative_to(ROOT)}: {name}")
    assert unlisted == [], "add these to studio/core/prompt_book.json"


def test_every_entry_reads_as_text():
    shown = [entry for group in prompt_book.read()["groups"] for entry in group["entries"]]
    assert len(shown) == len(ENTRIES)
    assert [e["source"] for e in shown if e.get("missing") or not e["text"].strip()] == []
    for entry in shown:
        assert entry["label"]["en"] and entry["label"]["zh"], entry["source"]


def test_a_named_line_reads_the_same_as_the_value_the_studio_runs_with():
    """The page reads lines without importing them; this imports them and compares."""
    for path, name in sorted(listed_lines()):
        if not path.startswith(("studio/", "evalkit/")):
            continue
        module = importlib.import_module(path.removesuffix(".py").replace("/", "."))
        assert prompt_book.constants(ROOT / path)[name] == getattr(module, name), f"{path}: {name}"


def test_wording_that_cannot_be_found_is_shown_as_missing_rather_than_dropped(tmp_path, monkeypatch):
    book = {"groups": [{"id": "g", "name": {"en": "G", "zh": "G"}, "entries": [
        {"file": "studio/prompts/no-such-prompt.txt", "label": {"en": "gone", "zh": "gone"}},
        {"code": "studio/making/sketch.py", "parts": ["NO_SUCH_LINE"], "label": {"en": "gone", "zh": "gone"}},
        {"code": "studio/making/sketch.py", "parts": ["ANNOTATE_SYSTEM"], "label": {"en": "here", "zh": "here"}}]}]}
    fake = tmp_path / "book.json"
    fake.write_text(json.dumps(book), encoding="utf-8")
    monkeypatch.setattr(prompt_book, "BOOK", fake)
    entries = prompt_book.read()["groups"][0]["entries"]
    assert [bool(e.get("missing")) for e in entries] == [True, True, False]
    assert entries[2]["text"] == "You annotate geometry. Return only the requested JSON."


def test_blanks_are_shown_as_blanks_between_the_named_lines():
    blank = "{output_language, entrance, lesson_context}"
    text = prompt_book.text_of({"code": "studio/conversation/teacher_review.py", "parts": ["MATERIALS_CLAUSE", blank]})
    assert text.endswith(blank) and len(text) > len(blank)


def test_the_safety_rules_are_cut_out_of_the_document_people_read():
    entry = next(e for e in ENTRIES if e.get("between"))
    text = prompt_book.text_of(entry)
    assert "policy:start" not in text and "policy:end" not in text and text.strip()
    assert Path(ROOT / entry["file"]).read_text(encoding="utf-8").count(text) == 1
