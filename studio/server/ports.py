"""Where this studio listens, and the one check that keeps it there.

Every port this product opens sits between 7000 and 7700 and ends in a zero.
The fixed unit digit is what makes one of ours recognisable at a glance in
`lsof`; the hundreds digit is section 7's memory grouping, so the number says
when a thing is loaded as well as where it answers:

    70x0  what a person opens: the page, the board, the preview
    71x0  the resident core, up for the whole class
    72x0  the resident media models
    73x0  the rotating slot, one at a time

The rule itself is stated and tested in tests/server/test_ports.py. This module exists
because a rule that only a test knows cannot say anything at the moment someone
starts a server outside it — which is how two of our own
servers came to be running on 8412 and 8767 with nothing objecting.

It reports and never refuses. A port typed on the command line is the operator's
choice; the failure being guarded against is not a wrong port, it is a wrong
port nobody sees.
"""

from __future__ import annotations

LOW, HIGH = 7000, 7700

# The four things a person opens. Each is written once, here.
PAGE_PORT = 7060
BOARD_PORT = 7010
PREVIEW_PORT = 7020
# The hackathon exhibit: the temple showpiece and the Harness page. It answered
# on 7090 from the day it was written and was the one human-facing port never
# registered here, so the number read as arbitrary to anybody who looked it up
# -- which is exactly what happened. Registered rather than
# renumbered: 7090 is already written into launch.json, the project snapshot
# and the measured records, and moving it would break every one of them to buy
# nothing.
EXHIBIT_PORT = 7090
WAN_PORT = 7260
TRELLIS_PORT = 7240
PIXAL_PORT = 7250
IMAGE_PORT = 7270
VOICE_PORT = 7280
HEARING_PORT = 7290   # Whisper on the 4090; the model board names it
# `studio/ops/voice_lab.py` still spells this one itself: at 620 lines it is over the
# size guard's hard limit and refuses writes, so it cannot be pointed here yet.
# The two are held together by a test rather than by an import.
VOICE_LAB_PORT = 7320
# The engineer's review: NVIDIA's Nemotron on the Spark, in the rotating slot. From the Mac the same
# address is an SSH tunnel to the hosted node, so one profile entry serves both.
ENGINEER_PORT = 7330
# NVIDIA's safety model beside the four-verdict check: small, resident for the whole class, so it
# sits with the resident core. `skills/studio-safety/scripts/nemotron_server.py` spells the same
# number, because a skill's script runs where this package is not installed; a test holds them together.
SAFETY_READER_PORT = 7140
# Qwen3.6, the class's first voice on the Spark (operator), resident beside the safety reader.
FRONT_VOICE_PORT = 7160


# Every port one of our own servers already owns. A port to suggest must not be
# one of these: once a busy 7060 was answered with "--port 7090", which
# by then was the exhibit's, so the advice moved you onto another server
# instead of off a busy one.
REGISTERED = frozenset({PAGE_PORT, BOARD_PORT, PREVIEW_PORT, EXHIBIT_PORT,
                        WAN_PORT, TRELLIS_PORT, PIXAL_PORT, IMAGE_PORT, VOICE_PORT,
                        HEARING_PORT, VOICE_LAB_PORT, ENGINEER_PORT,
                        SAFETY_READER_PORT, FRONT_VOICE_PORT})


def spare_port(busy: int) -> int:
    """A port worth suggesting when `busy` is taken.

    Inside the band, ending in zero, and not one another studio server already
    owns. It walks up from the busy port and wraps once at the top, so a request
    near HIGH is answered from the bottom of the band rather than outside it. If
    every port in the band were registered it would return the first step up
    regardless -- that cannot happen with nine registered out of seventy-one, and
    a suggestion is advice rather than a promise the port is free.
    """
    start = busy if LOW <= busy <= HIGH else PAGE_PORT
    for step in range(1, (HIGH - LOW) // 10 + 1):
        candidate = LOW + ((start - LOW) // 10 + step) % ((HIGH - LOW) // 10 + 1) * 10
        if candidate not in REGISTERED:
            return candidate
    return start + 10


def off_convention(port: int) -> str | None:
    """What is wrong with this port, or None if nothing is.

    Port 0 is exempt: it is how a test asks the operating system for a free
    port, and warning about it would train everyone to ignore the warning.
    """
    if port == 0:
        return None
    if not LOW <= port <= HIGH:
        return (f"Port {port} is outside the studio range {LOW}-{HIGH}. "
                f"Something else on this machine may already answer there.")
    if port % 10 != 0:
        return (f"Port {port} is inside the studio range {LOW}-{HIGH} but does not "
                f"end in a zero, so it will not read as one of ours in lsof.")
    return None
