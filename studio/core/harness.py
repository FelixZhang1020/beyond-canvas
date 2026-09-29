"""Run a request as stages, gate each one, and write down what happened.

This is the loop drawn in section 6: run, gate, append to the ledger, move on.
Failure at a gate retries once with the same inputs, then repairs, then stops
with a message a child can read. The three steps are different in kind and the
order matters — retrying a flaky call is cheap, changing the inputs is not, and
giving up is a product decision rather than an error.

Two properties are worth stating because they are easy to lose:

**A gate failure is not an exception.** A skill that produced something wrong
still produced something, and the ledger records the attempt. Only an
unreachable model raises.

**Resume reads the ledger, not memory.** A harness given a session name that
already has gate-passes recorded skips those stages, so a repeated request costs
at most one repeated stage.

It does NOT survive a restart, and section 10 should not be read as saying it
does. The session name is the request id, which is generated per request; the
class it belonged to lived in memory and is gone; and its conversations went with it, though the
Portfolio keeps the drawings. A one-off session
that keeps nothing has nothing to resume FROM. What this protects is a repeat
within a live class, which is the case that actually happens.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from studio.server import textstream
from studio.core.errors import ModelError, ModelRefused
from studio.core.ledger import Entry, Ledger, hash_inputs
from studio.core.metering import Meter, MediaMeter, Spend, used_memory_gb

RETRY_ONCE = 1

# How often the words a model is writing go to the page. A token arrives every few
# milliseconds and the page is sent the whole text each time (it replays from the
# start), so the text goes at most this often, and once more when the call ends.
WRITING_EVERY_S = 0.15


@dataclass(frozen=True)
class Stage:
    """One unit of work, and the check that decides whether it counted.

    `run` produces a result. `gate` says whether the result is acceptable, and
    returns a reason when it is not. `repair` gets one chance to change the
    inputs after a retry has already failed.
    """

    name: str
    skill: str
    run: Callable[[dict[str, Any]], Any]
    # Retries are for flakiness, not for decisions. A safety verdict sets this to
    # 0: re-rolling a refusal until it comes back "allow" is not a retry, it is
    # asking a different question until you like the answer.
    retries: int = RETRY_ONCE
    gate: Callable[[Any], tuple[bool, str]] = lambda result: (True, "no gate")
    repair: Callable[[dict[str, Any], str], dict[str, Any]] | None = None
    # Paid generation may have been accepted before a connection failed.
    # Such stages disable resubmission, independently of quality-gate retries.
    retry_model_errors: bool = True


@dataclass(frozen=True)
class Transition:
    """One thing the harness just did, told to whoever is watching.

    The page renders these as the steps a child can follow; a batch runner
    ignores them. `entry` is the ledger line the transition produced, when it
    produced one — a `running` transition has not been recorded yet.
    """

    stage: Stage
    status: str  # running | writing | checking | pass | fail | error | repair
    note: str = ""
    entry: Entry | None = None
    # Set on `writing` and `checking`: what the skill has written so far, or wrote,
    # before its gate has ruled. The page may show it as a draft; it is not a result.
    draft: str = ""


@dataclass
class StageOutcome:
    stage: str
    ok: bool
    result: Any = None
    reason: str = ""
    attempts: int = 0
    # True when the model could not be reached or returned nothing, as opposed
    # to a gate deciding the result was not good enough. A caller shows a child
    # different words for those two, and must be able to tell them apart.
    errored: bool = False


@dataclass
class Harness:
    """The scheduler. One request, several stages, one ledger."""

    ledger: Ledger
    session: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    stopped_with: str = ""
    # Called on every transition. Optional, because a batch run has no page.
    observe: Callable[[Transition], None] | None = None
    # The clients this run spends through. Everything they report is added up per
    # stage, which is how the ledger's tokens stopped being zero.
    meters: tuple[Meter | MediaMeter, ...] = ()

    def run(self, stages: list[Stage], inputs: dict[str, Any]) -> list[StageOutcome]:
        """Run stages in order, stopping at the first that cannot be salvaged."""
        done = self.ledger.completed_stages(self.session)
        outcomes: list[StageOutcome] = []
        for stage in stages:
            if stage.name in done:
                outcomes.append(StageOutcome(stage.name, ok=True, reason="already done"))
                continue
            outcome = self._one(stage, inputs)
            outcomes.append(outcome)
            if not outcome.ok:
                self.stopped_with = outcome.reason
                break
            inputs = {**inputs, stage.name: outcome.result}
        return outcomes

    def _one(self, stage: Stage, inputs: dict[str, Any]) -> StageOutcome:
        attempt_inputs = inputs
        reason = ""
        for attempt in range(1, stage.retries + 2):
            started, before_gb = time.monotonic(), used_memory_gb()
            self._notify(stage, "running")
            try:
                result = self._call(stage, attempt_inputs)
            except ModelError as error:
                self._record(
                    stage, attempt_inputs, "error", time.monotonic() - started, str(error), before_gb
                )
                return StageOutcome(stage.name, False, None, str(error), attempt, errored=True)
            self._checking(stage, result)
            ok, reason = stage.gate(result)
            self._record(
                stage,
                attempt_inputs,
                "pass" if ok else "fail",
                time.monotonic() - started,
                reason,
                before_gb,
            )
            if ok:
                return StageOutcome(stage.name, True, result, reason, attempt)

        if stage.repair is not None:
            self._notify(stage, "repair", reason)
            repaired = stage.repair(attempt_inputs, reason)
            started, before_gb = time.monotonic(), used_memory_gb()
            self._notify(stage, "running")
            try:
                result = self._call(stage, repaired)
            except ModelError as error:
                self._record(
                    stage, repaired, "error", time.monotonic() - started, str(error), before_gb
                )
                return StageOutcome(
                    stage.name, False, None, str(error), stage.retries + 2, errored=True
                )
            self._checking(stage, result)
            ok, reason = stage.gate(result)
            self._record(
                stage, repaired, "pass" if ok else "fail",
                time.monotonic() - started, reason, before_gb,
            )
            if ok:
                return StageOutcome(stage.name, True, result, reason, stage.retries + 2)

        return StageOutcome(stage.name, False, None, reason, stage.retries + 1)

    def _call(self, stage: Stage, inputs: dict[str, Any]) -> Any:
        """Run the skill, retrying a model error exactly once.

        This is separate from `stage.retries`, which governs a failed gate. A
        verdict must not be re-rolled — that is what retries=0 on the safety
        stage protects — but an empty reply or an unreachable endpoint is not a
        verdict, it is the model failing to answer, and one more ask is cheap.
        Found by a live run where a 147-second empty reply on the safety stage
        was treated as a decision.
        """
        try:
            with self._writing(stage):
                return stage.run(inputs)
        except ModelRefused:
            # A refusal is not a flaky answer: the endpoint rejected the request,
            # or the teacher stopped it. The same call again gets the same answer
            # at twice the wait and twice the bill.
            raise
        except ModelError:
            if not stage.retry_model_errors:
                raise
            with self._writing(stage):
                return stage.run(inputs)

    @contextmanager
    def _writing(self, stage: Stage) -> Iterator[None]:
        """Tell the watcher the words as the skill's model writes them (studio/server/textstream.py).

        Only for a stage the watcher asks for by `wants_text`: the page wants the words
        of a report or a reply, not a safety verdict or the numbers of a 3D figure, and
        a provider streams only when someone listens.
        """
        wants = getattr(self.observe, "wants_text", None)
        if self.observe is None or wants is None or not wants(stage):
            yield
            return
        written, sent, at = "", "", 0.0

        def show(text: str) -> None:
            nonlocal written, sent, at
            written = text
            if time.monotonic() - at >= WRITING_EVERY_S:
                sent, at = text, time.monotonic()
                self._notify_writing(stage, text)

        with textstream.listening(show):
            yield
        if written and written != sent:
            self._notify_writing(stage, written)

    def _notify_writing(self, stage: Stage, text: str) -> None:
        if self.observe is not None and text.strip():
            self.observe(Transition(stage, "writing", draft=text))

    def _notify(self, stage: Stage, status: str, note: str = "", entry: Entry | None = None) -> None:
        if self.observe is not None:
            self.observe(Transition(stage, status, note, entry))

    def _checking(self, stage: Stage, result: Any) -> None:
        """Tell the watcher what was written while the gate is still judging it.

        The rubric's judges take 12-37 s on the Spark against 5 s for the writing
        (measured), and before this the page showed nothing. Only text
        is offered; a verdict or a media result is not something to preview.
        """
        if self.observe is not None and isinstance(result, str) and result.strip():
            self.observe(Transition(stage, "checking", draft=result))

    def _record(
        self,
        stage: Stage,
        inputs: dict[str, Any],
        gate: str,
        elapsed: float,
        note: str,
        before_gb: float = 0.0,
    ) -> None:
        spent = Spend()
        for meter in self.meters:
            spent = spent + meter.take()
        entry = self.ledger.append(
            Entry(
                session=self.session,
                stage=stage.name,
                skill=stage.skill,
                gate=gate,
                # The ITEMS, not the keys. This used to hash the field
                # names, so every drawing in every class ever run shared one of
                # two fingerprints and the field proved nothing at all.
                inputs_hash=hash_inputs(sorted(inputs.items())),
                tokens=spent.tokens,
                cost_usd=spent.cost_usd,
                wall_time_s=round(elapsed, 3),
                memory_before_gb=before_gb,
                memory_after_gb=used_memory_gb(),
                note=note[:200],
            )
        )
        self._notify(stage, gate, note, entry)
