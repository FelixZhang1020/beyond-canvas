"""Reference-informed teacher commentary, independent of child dialogue."""
import json
import re
from pathlib import Path

from studio.core.errors import ModelCancelled

PROMPT = Path(__file__).parents[1] / 'prompts' / 'teacher-review.txt'
# Named, not written into the calls, so the prompt page in system management can show them.
MATERIALS_CLAUSE = '\n资料：'


def prompt(language, entrance, lesson):
    return PROMPT.read_text(encoding='utf-8') + MATERIALS_CLAUSE + json.dumps(
        {'output_language': 'Chinese' if language == 'zh' else 'English',
         'entrance': entrance, 'lesson_context': lesson}, ensure_ascii=False)


# The prompt asks for three paragraphs of about 300-500 Chinese characters, or
# 180-280 English words, and it says "about". So the gate is that range widened
# by a fifth rather than the range itself: it exists to reject a conversational
# one-liner and a runaway wall of text, not to police a report that runs a
# paragraph long. The one report accepted against a real drawing
# was 535 characters, which is why the ceiling is not the documented 500.
#
# Measuring characters for English was the defect this replaced: 100 Latin
# letters is about twenty words, so a two-sentence reply passed as a complete
# teacher report. Each language is counted in the unit it is written in.
TARGET = {'zh': (300, 500), 'en': (180, 280)}
SLACK = .2
CHINESE = re.compile(r'[\u4e00-\u9fff]')
LATIN = re.compile(r'[A-Za-z]')
WORD = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*")


def size(text, language):
    """How long the report is, in the unit that language is written in."""
    return len(CHINESE.findall(text)) if language == 'zh' else len(WORD.findall(text))


def check(text, language):
    if not isinstance(text, str) or not text.strip():
        return False, 'teacher commentary must be a complete, bounded report'
    if '?' in text or '？' in text:
        return False, 'teacher commentary must not ask the child questions'
    # Language first: a report in the wrong language would otherwise be reported
    # as the wrong length, measured in a unit it does not use.
    chinese, latin = len(CHINESE.findall(text)), len(LATIN.findall(text))
    if language == 'zh':
        if not chinese or latin > chinese * .1:
            return False, 'teacher commentary must use Chinese'
    elif chinese or not latin:
        return False, 'teacher commentary must use English'
    low, high = TARGET['zh' if language == 'zh' else 'en']
    if not low * (1 - SLACK) <= size(text, language) <= high * (1 + SLACK):
        return False, 'teacher commentary must be a complete, bounded report'
    return True, 'complete teacher commentary, without dialogue questions'


def write(client, image, language, entrance, lesson, cancelled=lambda: False):
    # One pass (operator). A draft, an independent critique and
    # a rewrite took 54 s in a class on the Spark, most of it the second and third
    # calls; a single draft measured 10-19 s. The report is read by the teacher,
    # an adult who decides what reaches the child, so the extra passes bought the
    # least there. check() still refuses a question, the wrong language and a
    # report outside its bounds, and the harness retries that once.
    #
    # Checked before the call as well: a retry after a stop re-enters here, and
    # must not spend a draft to discover it was stopped.
    if cancelled():
        raise ModelCancelled('Teacher review cancelled')
    text = client.chat(prompt(language, entrance, lesson), [image]).text.strip()
    if cancelled():
        raise ModelCancelled('Teacher review cancelled')
    return text
