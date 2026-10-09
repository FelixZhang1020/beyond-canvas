"""A storybook's pages redrawn in a picture-book style, the teacher's other way to make a book.

Operator: a teacher makes the book either of the child's originals (a drawing or its clip on each
page) or all redrawn by FLUX.2 Klein 4B on the Spark in one style, looking like a published book. The teacher
sees page 1 in every style first and picks one; the rest of the book is then drawn in it.

What keeps a redraw the child's picture: the class's vision model first lists what each drawing must keep (every
character with its colours, the sky), and that list goes into the instruction. Without it FLUX dropped a small
princess and turned grey mice brown in every style tried; with it every character stayed in all four styles
(docs/measured/storybook-styles.md). Every redraw is then screened like any picture a child sees,
and the vision model compares it with the original; a page of the book that lost, changed or added something is
drawn once more with another seed, and one still off after that is marked, for the teacher to see and decide.

Page 1's samples, one in each style, are drawn once and only marked (operator: faster books). Of seven samples
six were flagged and drawn again, 38 s for a choice that keeps one, and the second draw fixed none of them; the
sample she picks gets its second try beside the rest of the book instead. And while she reads the story, FLUX is
loaded and each drawing's list written (prepare), which her first press used to wait for (~23 s and ~3 s a page).

Nothing here writes about the child into the record: the ledger keeps counts and codes, and the lists and the
comparison's words stay in memory.
"""

from __future__ import annotations

import base64
import functools
import io
import json
import re
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from PIL import Image

from studio.core.errors import ModelError
from studio.core.harness import Harness, Stage
from studio.core.metering import MediaMeter, carried

ASSETS = Path(__file__).resolve().parents[2] / "skills/drawings-to-storybook/assets"
KEEP_PROMPT = ASSETS / "prompts/picture-keep.txt"
COMPARE_PROMPT = ASSETS / "prompts/picture-compare.txt"
SKILL = "book-pictures"
# One job on the Spark's picture service holds this many pictures (media_server.MOST_PICTURES).
MOST = 8
FIRST_SEED, AGAIN_SEED = 42, 43
# How long a check waits for NVIDIA's second reader if the job made it step aside (conversation.READER_BACK_S).
READER_BACK_S = 90
# One redraw at a time for the whole studio: the picture service takes one job and refuses the next, so a
# second class is told at once that the studio is busy instead of after a queue it cannot see.
_DRAWING = threading.Lock()
# While the teacher reads the story, one blank page this wide asks the Spark to load FLUX (prepare). It is drawn
# in well under a second and goes through the same door as a book's pages, so the picture service needs nothing
# new, and no child's drawing is sent for it.
WARM_SIDE = 64
# How long page 1 waits for that load before asking anyway: flux_client.LOAD_S, and a little more.
READY_WAIT_S = 200


@cache
def _table() -> dict:
    return json.loads((ASSETS / "picture-styles.json").read_text(encoding="utf-8"))


def styles() -> tuple[str, ...]:
    """The looks a teacher can choose, in the order she sees them."""
    return tuple(_table()["styles"])


def instruction(style: str, keep: str) -> str:
    table = _table()
    return table["instruction"].replace("{style}", table["styles"][style]).replace("{keep}", keep.strip())


def jpeg(data_uri: str) -> str:
    """A drawing as a JPEG of 1024 on its long side: the worker draws at that size, and the class keeps each
    drawing as a PNG of about a megabyte, seven of which would pass the picture service's request limit."""
    with Image.open(io.BytesIO(base64.b64decode(data_uri.partition(",")[2]))) as opened:
        image = opened.convert("RGB")
    image.thumbnail((1024, 1024))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


@cache
def blank() -> str:
    """The warm-up's page: white, WARM_SIDE across, as a JPEG like every page the worker is sent."""
    out = io.BytesIO()
    Image.new("RGB", (WARM_SIDE, WARM_SIDE), "white").save(out, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def kept(text: str) -> bool | None:
    """The comparison's answer: True or False, or None when it gave nothing readable, which is not a finding.

    Read from the answer's first words, not by parsing it whole: a long list of reasons can be cut off at the
    word limit, and in one trial three of eight answers were, each after a plain "kept": false."""
    found = re.search(r'"kept"\s*:\s*(true|false)', text)
    return None if found is None else found.group(1) == "true"


class Busy(Exception):
    """Another class's pages are being drawn."""


class Failed(Exception):
    """The pictures could not be made or shown; `code` is the reason the page and the record carry."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class Page:
    drawing_id: str
    style: str
    seed: int = FIRST_SEED
    url: str = ""
    safe: bool = False
    kept: bool | None = None

    @property
    def done(self) -> bool:
        return self.safe and self.kept is not False

    @property
    def again(self) -> bool:
        """Whether this is the page's second try, after which it is only marked, never drawn a third time."""
        return self.seed == AGAIN_SEED


class Drawing:
    """One request's pictures: the drawings' conversations, the painter, and the stages the record keeps.
    `quiet` for the lists written ahead (prepare), which no request on the page is waiting to hear about."""

    def __init__(self, conversations: dict, painter, keep_lists: dict[str, str], request_id: str,
                 quiet: bool = False) -> None:
        first = next(iter(conversations.values()))
        self.conversations, self.keep_lists, self.wanted = conversations, keep_lists, []
        self.painter_meter = MediaMeter(painter.client)
        self.painter = replace(painter, client=self.painter_meter)
        self.safety, self.screener, self.second = first.safety, first.screener, first.second_look
        # The class's checking model (vlm.director, temperature 0.1) lists and compares, not the writer (0.6).
        # With the writer's lists FLUX painted a purple-dressed princess red in all four styles,
        # which it had not with lists written at low temperature, and the writer's comparison listed the style
        # itself as changes, differently each time it was asked (docs/measured/storybook-styles.md).
        self.looker = first.director
        self.harness = Harness(first.ledger, session=request_id, observe=None if quiet else first.observe,
                               meters=(first.director, first.screener, self.painter_meter))
        self.originals = {did: jpeg(c.image) for did, c in conversations.items()}

    def stage(self, name: str, run, gate, *, model_errors: bool = True):
        # Which drawings and styles, so each job's line has its own fingerprint (ids, never content).
        inputs = {"beat": name, "pictures": sorted(self.wanted)}
        outcome = self.harness.run([Stage(name, SKILL, run, gate=gate, retries=0,
                                          retry_model_errors=model_errors)], inputs)[0]
        if not outcome.ok:
            raise Failed("model_unavailable" if outcome.errored else "pictures_unusable")
        return outcome.result

    def keep(self, drawing_ids) -> None:
        """Write the list of what each drawing must keep, where it has none yet in this sitting."""
        missing = [did for did in dict.fromkeys(drawing_ids) if not self.keep_lists.get(did)]
        if missing:
            self.wanted = self.wanted or [(did, "") for did in missing]
            self.keep_lists.update(self.stage("picture-keep", lambda _: self._keep(missing),
                                              lambda lists: (all(t.strip() for t in lists.values()), "listed")))

    def make(self, wanted: list[tuple[str, str]], again: Sequence[tuple[str, str]] = (),
             choosing: bool = False) -> list[Page]:
        """Draw `wanted`, and the pages in `again` once more: a sample she chose that the check had flagged.

        `choosing` is page 1 in several styles for her to choose from: drawn once, what changed only marked."""
        self.wanted = [*wanted, *again]
        self.keep(did for did, _ in self.wanted)
        fresh = [Page(did, style) for did, style in wanted]
        pages = fresh + [Page(did, style, AGAIN_SEED) for did, style in again]
        self._draw(pages, "picture-book")
        self._check(pages, "picture-check")
        # A sample that failed its screen is still drawn again: it has no picture to show at all.
        redo = [page for page in fresh if not page.safe or (not choosing and not page.done)]
        if redo:
            first = [(page.url, page.kept) if page.safe else None for page in redo]
            for page in redo:
                page.seed = AGAIN_SEED
            self._draw(redo, "picture-book-again")
            self._check(redo, "picture-check-again")
            for page, kept_first in zip(redo, first):   # a second try not safe to show gives back the safe first
                if kept_first and not page.safe:
                    (page.url, page.kept), page.safe = kept_first, True
        # A style that failed its screen twice is left out: page 1 still offers the others. A drawing left with no
        # picture at all cannot be a page of the book in that style; one drawn again keeps its first, flagged page.
        pages = [page for page in pages if page.safe]
        if {did for did, _ in wanted} - {page.drawing_id for page in pages}:
            raise Failed("book_picture_held_back")
        return pages

    def _keep(self, drawing_ids: list[str]) -> dict[str, str]:
        prompt = KEEP_PROMPT.read_text(encoding="utf-8")

        def one(did):
            return self.looker.chat(prompt, [self.originals[did]], max_tokens=700).text.strip()[:2000]
        # Wrapped here, on the request's thread: a pool thread starts with no request to count against.
        calls = [carried(functools.partial(one, did)) for did in drawing_ids]
        with ThreadPoolExecutor(max_workers=4) as pool:
            return dict(zip(drawing_ids, pool.map(lambda call: str(call()), calls)))

    def _draw(self, pages: list[Page], name: str) -> None:
        jobs = [{"image": self.originals[p.drawing_id], "instruction": instruction(p.style, self.keep_lists[p.drawing_id]),
                 "seed": p.seed} for p in pages]
        drawn = self.stage(name, lambda _: self.painter.restyle_pictures(jobs).payload.get("pictures", []),
                           lambda made: (len(made) == len(jobs), f"{len(made)} of {len(jobs)} drawn"), model_errors=False)
        for page, url in zip(pages, drawn):
            page.url, page.safe, page.kept = url, False, None

    def _check(self, pages: list[Page], name: str) -> None:
        compare = COMPARE_PROMPT.read_text(encoding="utf-8")
        getattr(self.second, "wait_ready", lambda seconds: None)(READER_BACK_S)

        def one(page: Page) -> None:
            verdict = self.safety.screen(page.url, self.screener, second=self.second, point="out")
            # The studio drew this picture, so a clay scene that reads as a photograph ("block", not artwork) is
            # not held back, as with the 3D figure (conversation.figure); harm still is.
            page.safe = verdict.may_proceed or verdict.verdict == "block"
            if page.safe:
                try:   # no answer is not a finding: the page is shown, and the record says it went unchecked
                    said = self.looker.chat(compare.replace("{keep}", self.keep_lists[page.drawing_id]),
                                            [self.originals[page.drawing_id], page.url], max_tokens=500).text
                except ModelError:
                    return
                page.kept = kept(said)

        def run(_):
            calls = [carried(functools.partial(one, page)) for page in pages]
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda call: call(), calls))
            return pages

        def gate(checked):
            count = lambda test: sum(1 for p in checked if test(p))
            return True, (f"{count(lambda p: p.safe)} of {len(checked)} screened safe; kept {count(lambda p: p.kept)}, "
                          f"changed {count(lambda p: p.kept is False)}, unchecked {count(lambda p: p.safe and p.kept is None)}")
        self.stage(name, run, gate)


def make(conversations: dict, wanted: list[tuple[str, str]], painter, keep_lists: dict[str, str],
         request_id: str, *, again: Sequence[tuple[str, str]] = (), choosing: bool = False) -> list[dict]:
    """Draw each (drawing, style) wanted, and each in `again` once more; raise Busy while another class draws,
    Failed when it cannot. `again` is the chosen samples the check flagged, `choosing` a job of samples (make).

    `conversations` holds the drawings' conversations, already screened."""
    if not 1 <= len(wanted) + len(again) <= MOST:
        raise ValueError(f"one to {MOST} pictures in one job")
    if not _DRAWING.acquire(blocking=False):
        raise Busy()
    try:
        pages = Drawing(conversations, painter, keep_lists, request_id).make(wanted, list(again), choosing)
    except ModelError:
        raise Failed("model_unavailable") from None
    finally:
        _DRAWING.release()
    return [{"drawing_id": p.drawing_id, "style": p.style, "url": p.url, "changed": p.kept is False,
             "again": p.again} for p in pages]


def warm(painter) -> bool:
    """Have the Spark load FLUX now, with one blank page (WARM_SIDE); False if it could not or need not.

    Not while another class draws, since FLUX is loaded then and the picture service would refuse a second job;
    a failure costs only the load it would have saved, as the first page's job loads it anyway."""
    if not _DRAWING.acquire(blocking=False):
        return False
    try:
        painter.restyle_pictures([{"image": blank(), "instruction": "A blank white page.", "seed": FIRST_SEED}])
        return True
    except Exception as error:   # the load it would have saved is all it costs; the first page's job loads FLUX
        print(f"book pictures: FLUX was not loaded ahead ({type(error).__name__})", flush=True)
        return False
    finally:
        _DRAWING.release()


def prepare(conversations: dict, painter, keep_lists: dict[str, str], request_id: str) -> None:
    """While the teacher reads the story: FLUX loaded, and the list of what each drawing must keep written.

    Both are what her first press used to wait for, and neither is shown, so a failure here costs only the time it
    would have saved. `conversations` holds the book's drawings' conversations, already screened (the story's own
    screen); the lists' lines go under the story's request, which the class forgets with the rest of its lines."""
    loading = threading.Thread(target=warm, args=(painter,), name="book-warm", daemon=True)
    loading.start()
    try:
        Drawing(conversations, painter, keep_lists, request_id, quiet=True).keep(list(conversations))
    except (Failed, ModelError) as error:   # page 1 writes its own list then, as it always did
        print(f"book pictures: the lists were not written ahead ({type(error).__name__})", flush=True)
    finally:
        loading.join()
