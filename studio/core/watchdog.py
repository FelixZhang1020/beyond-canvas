"""Refuse a model load that would freeze the box.

Section 2 states the failure: out of memory freezes the machine, and a load can
transiently cost twice its resident size. A freeze during a class is not a
degraded experience, it is the end of the class, so the watchdog refuses rather
than tries.

**Where the transient went.** The obvious implementation charges every load
twice its size, and it contradicts the spec's own arithmetic: a 57 GB resident
set plus a 30 GB big slot is stated as an 87 GB peak, which a doubling would
make 117. So the 90 GB ceiling is treated as already containing the allowance
rather than the transient being charged again on top of it.

How much of the gap between 90 and the 108 to 119 GB usable a real load needs is
NOT modelled here, because nothing has measured it. A full second copy of a
28 GB model on top of an 85 GB resident set would want 113 GB, which is over the
floor of that range — so whether the margin holds depends on whether loads
memory-map rather than copy, which is exactly what the container recipe's note
about disabling memory mapping is circling. Day zero settles it. Encoding a
guess here would be testing my arithmetic rather than the box.

**Director mode is outside the ceiling, not an exception to it.** Step 3.7
Flash at 109 GB cannot fit under 90 by any arithmetic. Section 7 unloads
everything else and takes the whole box, which is safe only because a child
session is never active then — the mode is the safety mechanism. It also has no
margin: 109 GB does not fit under the 108 GB floor of the usable range, so this
mode depends on the real figure landing nearer 119. A refusal here is the honest
answer rather than a bug.

The numbers are passed in rather than measured, so the state machine is
testable before a Spark exists — which is what section 7 asks for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Section 7. Studio mode is capped at 90 GB, comfortably below the 108 to 119 GB
# the box makes usable, and the gap is the transient allowance.
STUDIO_CEILING_GB = 90.0

# Director mode takes the whole box. The range is wide because section 2 gives it
# as 108 to 119 GB, and the 109 GB director model does not fit under the floor of
# that range — so this mode has no margin and depends on where the real figure
# lands. Day zero measures it; until then this is the optimistic end, and a load
# refused here is the honest answer rather than a bug.
USABLE_CEILING_GB = 119.0

# What the classroom may have in use before it refuses one more request (operator). The studio
# ceiling above plans model loads; the classroom used it too, and once the chat voice and TRELLIS.2 stayed
# loaded the box sat at 93.6 GB, so every request was refused as out of memory. With Wan 2.2 no longer run
# on the Spark, the operator judged the resident set safe together up to 115 GB.
CLASSROOM_CEILING_GB = 115.0


class WouldNotFit(Exception):
    """A load was refused. The caller degrades or switches mode; it does not retry."""


@dataclass
class Watchdog:
    """Tracks what is resident and decides what may join it."""

    ceiling_gb: float = STUDIO_CEILING_GB
    resident: dict[str, float] = field(default_factory=dict)
    director_mode: bool = False

    @property
    def used_gb(self) -> float:
        return round(sum(self.resident.values()), 3)

    @property
    def limit_gb(self) -> float:
        """Director mode gets the whole box, because nothing else is loaded."""
        return USABLE_CEILING_GB if self.director_mode else self.ceiling_gb

    @property
    def headroom_gb(self) -> float:
        return round(self.limit_gb - self.used_gb, 3)

    def peak_for(self, size_gb: float) -> float:
        return round(self.used_gb + size_gb, 3)

    def would_fit(self, size_gb: float) -> bool:
        return self.peak_for(size_gb) <= self.limit_gb

    def load(self, name: str, size_gb: float) -> None:
        """Admit a model, or refuse and say by how much it missed."""
        if name in self.resident:
            return
        if not self.would_fit(size_gb):
            raise WouldNotFit(
                f"loading {name} at {size_gb} GB would reach {self.peak_for(size_gb)} GB "
                f"against a {self.limit_gb} GB limit, with {self.headroom_gb} GB free; "
                "unload something or switch mode"
            )
        self.resident[name] = size_gb

    def unload(self, name: str) -> None:
        self.resident.pop(name, None)

    def swap(self, name: str, size_gb: float, slot_holder: str) -> None:
        """Unload before load. The order is the safety property, not a preference.

        Loading first and unloading after is the shape that freezes the machine,
        because both models are resident at the moment of peak. The big slot
        holds one of image.edit, mesh.premium or tts.export at a time for
        exactly this reason.
        """
        self.unload(slot_holder)
        self.load(name, size_gb)

    def enter_director_mode(self, name: str, size_gb: float) -> None:
        """Unload the studio entirely, then take the box.

        Never called while a child session is active. Section 7 is explicit
        about that, and it is the only thing making a 109 GB model acceptable.
        """
        self.resident.clear()
        self.director_mode = True
        self.load(name, size_gb)

    def restore_studio_mode(self) -> None:
        self.resident.clear()
        self.director_mode = False
