"""One drawing, held open while the child is still in the room.

This is the hero scenario assembled from the parts: screen the image, write the
opening, gate it against the rubric, and record every decision. Then keep the
drawing open for what comes next — the child's answer, or their silence —
because the reply and the rungs need the opening they follow, and only
something that stays alive between requests can remember it.

The order is section 6's and is not negotiable. Safety runs first, so a blocked
image never reaches a skill. The gate runs after the skill, so nothing a child
sees has gone unchecked.

A verdict is decided once per drawing. Screening the same bytes again on the
next beat would be re-rolling a decision, which is what retries=0 on the safety
stage exists to prevent — so the verdict is remembered, and a refused drawing
stays refused for as long as the conversation is open.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from evalkit.rubric import Entrance
from evalkit.rubric.report import RubricReport
from studio.core.harness import RETRY_ONCE, Harness, Stage, StageOutcome, Transition
from studio.core.images import to_data_uri
from studio.core.ledger import Ledger
from studio.core.metering import Meter, MediaMeter
from studio.providers.base import VisionChatClient
from studio.conversation.words import REASON_CODES, say
from studio.making import animation, sketch, figure as figures
from studio.server import textstream
from studio.providers.media import MediaSlot
from studio.core.errors import ModelError
from studio.conversation.chat_beats import ChatBeats
from studio.conversation.drafting import Drafting
# The floor and the strict-attempt count moved to gates.py with the gates that
# decide by them, and are re-exported: session.py and the retry tests read them
# from here, where they have always been.
from studio.conversation.gates import RUBRIC_FLOOR, STRICT_ATTEMPTS, Gates, Unreadable  # noqa: F401

# How long a clip's way-out look waits for NVIDIA's reader to load again after stepping aside for it (~12 s).
READER_BACK_S = 90
# And for Qwen, the screener: it loads again in about four minutes, and the 3D model (80 s) and the reader may
# take the GPU lock before it.
SCREENER_BACK_S = 420
ROOT = Path(__file__).resolve().parents[2]

_SKILLS: dict[str, Any] = {}


def _load_skill(name: str, relative: str):
    """Import a skill script by path, once, the way a harness would run it."""
    if name not in _SKILLS:
        path = ROOT / relative
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _SKILLS[name] = module
    return _SKILLS[name]


@dataclass
class Beat:
    """One turn the machine took: what to show, or why nothing is shown."""

    kind: str  # opening | reply | rung-2 | rung-3 | animation
    request_id: str = ""
    text: str = ""
    refused: str = ""
    reason_code: str = ""
    failed_rules: list[int] = field(default_factory=list)
    outcomes: list[StageOutcome] = field(default_factory=list)
    # Structured media output: a generated clip or a reconstructed scene.
    plan: dict | None = None
    draft: str | None = None  # Rejected editable candidate, never a passing result.
    issues: list[dict[str, str]] = field(default_factory=list)  # What the review flagged on that draft, for the teacher.

    @property
    def ok(self) -> bool:
        # A beat succeeded if it produced the thing it was for. Feedback
        # produces words; an animation produces a plan and no words at all.
        # Reading only `text` made a passing animation report itself as failed
        # and a child saw "Splat needs a little rest" over a plan the ledger had
        # already recorded as good. Found on the first live run through the page.
        return bool(self.text or self.plan) and not self.refused


class Conversation(ChatBeats, Drafting, Gates):
    """One drawing, screened once, with the opening remembered for what follows."""

    def __init__(
        self,
        drawing: str | Path,
        ledger: Ledger,
        *,
        entrance: Entrance,
        studio: VisionChatClient,
        director: VisionChatClient,
        language: str = "en",
        lesson_intent: str = "",
        screener: VisionChatClient | None = None,
        geometry: VisionChatClient | None = None,
        creation: VisionChatClient | None = None,
        figure: VisionChatClient | None = None,
        figure_look: VisionChatClient | None = None,
        editor: MediaSlot | None = None,
        portrait: MediaSlot | None = None,
        observe: Callable[[Transition], None] | None = None,
    ) -> None:
        self.drawing = str(drawing)
        self.ledger = ledger
        self.entrance = entrance
        # Both clients are metered, so a stage's ledger line carries what the
        # writer AND its judges spent. Checking a line costs more than writing
        # it, and a record that hid that was not worth reading.
        self.studio = Meter(studio)
        self.writer = Meter(studio.front) if getattr(studio, "front", None) else self.studio  # frontvoice.py
        self.creator = Meter(creation) if creation is not None else self.studio
        self.review_creation = creation is not None
        self.figurer = Meter(figure) if figure is not None else self.creator   # its own time limit, if any
        self.figure_looker = Meter(figure_look) if figure_look is not None else self.figurer  # the toy's check
        self.geometry = Meter(geometry) if geometry is not None else self.studio
        self.media_meter = MediaMeter(editor.client) if editor is not None else None
        self.editor = replace(editor, client=self.media_meter) if editor is not None else None
        self.portrait_meter = MediaMeter(portrait.client) if portrait is not None else None
        self.portrait = replace(portrait, client=self.portrait_meter) if portrait is not None else None
        self.director = Meter(director)
        # What the last independent draft review flagged, as evidence and
        # suggestion pairs. It rides on the beat to the teacher, who can act on
        # it; it never becomes a ledger note, because the reviewer is told to
        # compare the candidate with the child's words and the drawing, and
        # ledger.py's opening comment forbids either in a line.
        self.review_issues: list[dict[str, str]] = []
        # The same pairs, kept per kind of draft until that kind passes, so the
        # next attempt is told what to fix instead of being asked to reword a
        # guess. A scene's findings and an outline's findings are never the same
        # findings, and drawing zero's conversation runs both.
        self.carried_findings: dict[str, list[dict[str, str]]] = {}
        # The filter has its own small resident model on the box. Where a profile
        # names none, the director stands in, which is right in the cloud and
        # wrong on the Spark: section 7 forbids loading the director while a
        # child is waiting, and every drawing is screened while one is.
        self.screener = Meter(screener) if screener is not None else self.director
        # NVIDIA's safety model rides on the screener (providers/safetyreader.py says why).
        self.second_look = getattr(screener, "second", None)
        # Its wait too, read before the Meter: that counts calls and passes nothing else on (code review).
        self.screener_back = getattr(screener, "wait_ready", lambda seconds: None)
        self.language = language
        self.lesson_intent = lesson_intent
        self.observe = observe
        self.image = to_data_uri(drawing)
        self.verdict: Any = None
        self.opening = ""
        self._report: RubricReport | None = None
        # One successful clip per drawing and set of words, kept for this conversation.
        # Replaying unchanged input must not run the video model again.
        self._animation: tuple[str, Any] | None = None
        self._clip_tries = 0
        self._figure: dict | None = None
        self._sketch_scene: dict | None = None
        self._sketch_scenes: dict[str, dict] = {}
        self.safety = _load_skill("safety_skill", "skills/studio-safety/scripts/safety.py")
        self.feedback = _load_skill("feedback_skill", "skills/art-feedback/scripts/feedback.py")
        self.motion = _load_skill(
            "choreograph_skill", "skills/painting-to-animation/scripts/choreograph.py"
        )
        self.clip_check = _load_skill("clip_check_skill", "skills/painting-to-animation/scripts/clip_check.py")
        self.settings = self.feedback.ClassSettings(entrance, language, lesson_intent)

    # The beats (the chat three are in chat_beats.py) ------------------------

    def animate(self, child_said: str = "", request_id: str = "") -> Beat:
        """Generate and screen a short Wan preview from the original drawing."""

        child_said = child_said.strip()[:600]
        cache_key = (child_said, getattr(self, "clip_maker", None))   # set per request (classroom_runs)
        held_back = False

        def write(inputs: dict[str, Any]):
            if self._animation is not None and self._animation[0] == cache_key:
                return self._animation[1]
            # The first clip keeps the service's own start (42, what was measured). A new try after a
            # held-back clip must start elsewhere, or it would paint the same hands again.
            self._clip_tries += 1
            seed = None if self._clip_tries == 1 else 41 + self._clip_tries
            try:
                return animation.generate(self.image, child_said, self.editor, seed, cache_key[1])
            except (ValueError, TypeError):
                return Unreadable("invalid generated media")

        def check(frame):
            nonlocal held_back
            if isinstance(frame, Unreadable):
                return False, frame.why
            if self._animation is not None and frame is self._animation[1]:
                return True, "cached media; visual fidelity requires teacher review"
            # Input screening still precedes generation. Screen the generated
            # picture too; the paid result stays fixed throughout screening. Qwen, which screens every frame,
            # and NVIDIA's reader both stepped aside for this clip's memory; the looks wait for each to load
            # again (the door never waits). Without Qwen's wait every Spark clip was refused unscreened.
            self.screener_back(SCREENER_BACK_S)
            getattr(self.second_look, "wait_ready", lambda seconds: None)(READER_BACK_S)
            looks = []
            try:
                for picture in getattr(frame, "screen_images", (frame.image,)):
                    verdict = self.safety.screen(picture, self.screener, second=self.second_look, point="out")
                    looks.append(verdict)
                    if not _screen_gate(verdict)[0]:
                        # The second look's codes, when there was one, after the words the record has always used.
                        said = getattr(verdict, "ledger_note", "").partition(" ")[2]
                        return False, " ".join(filter(None, ["generated media safety fail", said]))
            except ModelError:
                return False, "generated image safety unavailable"
            # Every frame passed the screen above (a failing one returned). Safe, then faithful: a real
            # hand or art tool Wan painted in holds the clip back. No answer is not a finding; the clip
            # is shown and the record says it went unchecked.
            found = self.clip_check.check(self.image, frame.screen_images, self.screener)
            if found:
                held_back = True
                return False, f"clip check fail{_looked(looks)}: " + " ".join(found)
            checked = "unavailable" if found is None else "pass"
            return True, (f"clip safety pass{_looked(looks)}; clip check {checked}; "
                          "visual fidelity requires teacher review")

        beat = self._beat(
            "animation",
            write,
            check,
            request_id,
            redact=False,
            retries=0,
            retry_model_errors=False,
        )
        if beat.ok:
            self._animation = (cache_key, beat.text)
            beat.plan = beat.text.as_dict()
            beat.text = ""
        elif held_back:
            beat.refused, beat.reason_code = say(self.language, "clip_held_back"), "clip_held_back"
        return beat

    def figure(self, request_id: str = "", cancelled=lambda: False) -> Beat:
        """A 3D toy figure inspired by the painting, made and checked once per drawing (studio/making/figure.py).
        A screening outage travels out as an outage: the figure is never shown, and the teacher is told why."""
        held_back, looks = False, []

        def screen(preview):
            verdict = self.safety.screen(preview, self.screener, second=self.second_look, point="out")
            looks.append(verdict)
            # The studio drew this toy itself, so it is never a photograph: "block" (not artwork) does not hold it
            # back, as Qwen's screen did to a harmless teddy bear (operator). Harm still does.
            return _screen_gate(verdict)[0] or verdict.verdict == "block"

        def write(inputs):
            nonlocal held_back
            if self._figure is not None:
                return self._figure
            made = figures.make(self.image, self.figurer, screen, cancelled, self.figure_looker)
            held_back = made["held_back"]
            return Unreadable("figure held back") if held_back else made["figure"]

        beat = self._beat("figure", write,
                          lambda made: (not isinstance(made, Unreadable), "parts bounded, settled, screened"
                                        + _looked(looks[-1:] if not isinstance(made, Unreadable) else looks)
                                        + " and looked at"),   # a shown figure: by the look it passed
                          request_id, redact=False, retries=0, retry_model_errors=False)
        if beat.ok:
            self._figure = beat.text
            beat.plan, beat.text = self._figure, ""
        elif held_back:
            beat.refused, beat.reason_code = say(self.language, "figure_held_back"), "figure_held_back"
        return beat

    def reconstruct(self, request_id: str = "", model_choice: str = "auto", *, regenerate: bool = False) -> Beat:
        """Reuse a chosen result on retry; an explicit regeneration runs the model again."""
        unsupported = False
        portrait_unavailable = False
        fruit_unavailable = False

        def write(inputs):
            nonlocal unsupported, portrait_unavailable, fruit_unavailable
            if not regenerate and model_choice in self._sketch_scenes:
                return self._sketch_scenes[model_choice]
            try:
                return sketch.reconstruct(self.drawing, self.geometry, self.portrait, model_choice=model_choice)
            except sketch.PortraitUnavailable:
                portrait_unavailable = True
                raise
            except sketch.FruitMeshUnavailable:
                fruit_unavailable = True
                raise
            except sketch.UnsupportedSketch:
                unsupported = True
                return Unreadable("unsupported geometry")
            except (ValueError, TypeError):
                # Do not log raw model output or parsing errors containing it.
                return Unreadable("invalid scene data")

        beat = self._beat("reconstruction", write,
                          lambda scene: (not isinstance(scene, Unreadable), "bounded geometry check"),
                          request_id, redact=False, retries=0, retry_model_errors=False)
        if beat.ok:
            self._sketch_scene = beat.text
            self._sketch_scenes[model_choice] = beat.text
            beat.plan, beat.text = self._sketch_scene, ""
        elif portrait_unavailable:
            beat.refused, beat.reason_code = say(self.language, "portrait_unavailable"), "portrait_unavailable"
        elif fruit_unavailable:
            beat.refused, beat.reason_code = say(self.language, "fruit_mesh_unavailable"), "fruit_mesh_unavailable"
        elif unsupported:
            beat.refused, beat.reason_code = say(self.language, "sketch_unsupported"), "unsupported_geometry"
        elif beat.reason_code == "rubric_failed":
            beat.refused, beat.reason_code = say(self.language, "sketch_invalid"), "invalid_scene"
        return beat

    # The loop ----------------------------------------------------------------

    def teacher_review(self, client, request_id="", cancelled=lambda: False):
        from studio.conversation import teacher_review
        meter = Meter(client)
        # One retry, and model errors retried too. A report that comes out past
        # its length bound, or a completion Step 3.7 Flash spent on hidden
        # reasoning and returned empty, is not a verdict about the child that
        # must never be re-rolled; it is the flaky call the harness's retry
        # exists for. In one live run a drawing hit both, on two presses,
        # and the teacher was shown the hiccup line twice.
        return self._beat("teacher-review",
            lambda _: teacher_review.write(meter, self.image, self.language,
                self.entrance, self.lesson_intent, cancelled),
            lambda text: teacher_review.check(text, self.language), request_id,
            retries=RETRY_ONCE, retry_model_errors=True, extra_meters=(meter,))

    def _beat(
        self, kind: str, write, gate, request_id: str, *, redact: bool = True, repair=None,
        retries: int = RETRY_ONCE, retry_model_errors: bool = True,
        namespace: str = "", extra_meters=(),
    ) -> Beat:
        if self.verdict is not None and not self.verdict.may_proceed:
            return self._refused(Beat(kind, request_id), errored=False)

        stages: list[Stage] = []
        screen_name = f"screen-{namespace}" if namespace else "screen"
        beat_name = f"{kind}-{namespace}" if namespace else kind
        if self.verdict is None:
            stages.append(
                Stage(screen_name, "studio-safety", self._screen, gate=_screen_gate, retries=0)
            )
        skill = {"animation": "painting-to-animation", "figure": "painting-to-figure",
                 "scene-description": "scene-description", "story-outline": "story-outline",
                 "teacher-review": "teacher-review",
                 "reconstruction": "sketch-to-3d",
                 "storybook-page": "drawings-to-storybook"}.get(kind, "art-feedback")
        runner = self._redacting(write) if redact else write
        stages.append(Stage(beat_name, skill, runner, gate=gate, repair=repair, retries=retries,
                            retry_model_errors=retry_model_errors))

        meters = {id(m): m for m in (self.studio, self.director, self.screener, self.geometry, self.creator,
                                     self.figurer, self.writer, *extra_meters)}
        if self.media_meter is not None:
            meters[id(self.media_meter)] = self.media_meter
        if self.portrait_meter is not None:
            meters[id(self.portrait_meter)] = self.portrait_meter
        harness = Harness(self.ledger, observe=self.observe, meters=tuple(meters.values()))
        if request_id:
            harness.session = request_id
        outcomes = harness.run(stages, {"drawing": self.drawing, "beat": kind})
        beat = Beat(kind, harness.session, outcomes=outcomes)

        screened = next((o for o in outcomes if o.stage == screen_name), None)
        if screened is not None and not screened.ok:
            return self._refused(beat, errored=screened.errored)

        written = next((o for o in outcomes if o.stage == beat_name), None)
        if written is not None and written.ok:
            beat.text = written.result
        elif written is not None and written.errored:
            beat.refused, beat.reason_code = say(self.language, "hiccup"), "model_unavailable"
        else:
            beat.refused, beat.reason_code = say(self.language, "gate"), "rubric_failed"
        if self._report is not None:
            beat.failed_rules = [failure.rule for failure in self._report.failures]
        return beat

    def _refused(self, beat: Beat, *, errored: bool) -> Beat:
        # An errored screen is not a verdict. A model that returned nothing has
        # said nothing about the drawing, and telling the child "this does not
        # look like a drawing" on that basis is the filter inventing a refusal.
        # Found by a live run, where a 147-second empty reply on
        # the monster drawing came back wearing the block message.
        if errored or self.verdict is None:
            beat.refused, beat.reason_code = say(self.language, "hiccup"), "model_unavailable"
            return beat
        verdict = self.verdict.verdict
        beat.refused = say(self.language, verdict if verdict in REASON_CODES else "block")
        beat.reason_code = REASON_CODES.get(verdict, "photo_not_drawing")
        return beat

    def _screen(self, inputs: dict[str, Any]):
        self.verdict = self.safety.screen(self.image, self.screener, second=self.second_look)
        return self.verdict

    def _redacting(self, write):
        """Strip anything written on the page out of what is about to be shown."""

        def run(inputs: dict[str, Any]) -> str:
            found = self.verdict.text_found if self.verdict is not None else ()
            with textstream.shown_as(lambda text: textstream.unfinished_cut(self.safety.redact(text, found), found) if found else text):
                text = write(inputs)   # the words shown while they are written are redacted too
            return self.safety.redact(text, found) if found else text

        return run


def _looked(verdicts: list) -> str:
    """What NVIDIA's second look said of made pictures, for the record: nothing without a reader, the
    codes of anything it flagged, else "unavailable" if any look could not be taken, else "clear"."""
    said = [getattr(v, "second_look", "") for v in verdicts]
    flagged = dict.fromkeys(c for v in verdicts if getattr(v, "second_look", "") == "flagged"
                            for c in getattr(v, "teacher_codes", ()))
    if flagged:
        return " second-look:" + ",".join(flagged)
    return " second-look:" + ("unavailable" if "unavailable" in said else "clear") if any(said) else ""


def _screen_gate(verdict) -> tuple[bool, str]:
    """The verdict, and not the sentence describing the drawing.

    The reason is a model's description of a child's picture — "a crayon drawing
    of a house, tree, sun and grass" — and it was written into a permanent file
    that outlived the class. The ledger's own opening comment forbids exactly
    that. The teacher still sees the full reason on screen; the record keeps the
    decision.
    """
    return verdict.may_proceed, getattr(verdict, "ledger_note", verdict.verdict)
