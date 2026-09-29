"""The two pushes of the shake test, frame by frame. First the ground moves: a sine wave along one
horizontal line that swells for half a second, holds, fades, and leaves the ground exactly
where it began, so what moved is measured against where it started. Then, after a pause, a steady
sideways pull swells, holds and lets go: the engineer's tilt table, which finds what a wave this
quick cannot, because the wave moves the ground only millimetres. The pull is the same code's
frequent earthquake, the level at which a building should take no damage at all; at the design
peak held steady the real temple's own model creeps and tips, because its joints are
drawn as resting, not as the stiff mortises they are, so that level cannot be asked of a hall. Still for LEAD seconds first and REST seconds after. The steady waves push at exactly the
peak; while they swell and fade the push runs up to a tenth higher, which errs on the hard side.

The numbers are the Foguang hall's own site in China's seismic design code GB 50011-2010 (2016
edition), not a judgement of ours. It is one steady wave, not a recorded earthquake, and the joints
are as simple as the settle test's: this finds what is only balanced, it does not certify a hall.
Plain Python, no Blender.
"""
import math

G = 9.81
LEAD, REST, SWELL = 0.25, 1.0, 0.5    # every second is baked at 1,440 steps, so none is spent idle
PAUSE, PULL_HOLD = 0.25, 1.5
SECONDS = 6.0                           # still, two seconds of shaking, the pull, still again
PULL = PAUSE + SWELL + PULL_HOLD + SWELL     # the pull's whole block, the pause before it included
SITE = {
    "peak_g": 0.20,   # design basic acceleration of ground motion: the shaking
    "pull_g": 0.07,   # peak acceleration of the frequent earthquake at intensity 8, 70 cm/s2: the steady pull
    "hz": 2.5,        # one over the characteristic period, 0.40 s
    "degrees": 45.0,  # along the plan's diagonal, so both rows of columns are pushed
    "source": "GB 50011-2010 (2016 edition): appendix A lists Wutai county, Xinzhou, Shanxi at intensity 8, "
              "0.20 g, group 2; table 5.1.4-2 gives group 2 on class II ground a characteristic period of 0.40 s; "
              "table 5.1.2-2 gives the frequent earthquake at intensity 8 a peak of 70 cm/s2",
}


def shaking_seconds(frames, fps):
    shaking = frames / fps - LEAD - PULL - REST
    if shaking < 1.0:
        raise SystemExit(f"the shake test needs at least {LEAD + PULL + REST + 1.0} seconds: still, a second or "
                         f"more of shaking, the steady pull, still again")
    return shaking


def ground_path(frames, fps, peak_g, hz):
    """The ground's offset along its line, in metres, at each frame from the first."""
    amplitude = peak_g * G / (2 * math.pi * hz) ** 2
    shaking = shaking_seconds(frames, fps)
    swell = min(SWELL, shaking / 4)
    path = []
    for frame in range(frames):
        t = frame / fps - LEAD
        if t <= 0 or t >= shaking:
            path.append(0.0)
            continue
        ease = min(1.0, t / swell, (shaking - t) / swell)
        path.append(amplitude * (math.sin(math.pi * ease / 2) ** 2) * math.sin(2 * math.pi * hz * t))
    return path


def sideways_pull(frames, fps, pull_g):
    """The steady pull at each frame, in g: nothing until the shaking and the pause are over, then up
    over SWELL seconds, held, and down again, leaving REST seconds of stillness."""
    begins = LEAD + shaking_seconds(frames, fps) + PAUSE
    pull = []
    for frame in range(frames):
        t = frame / fps - begins
        ease = max(0.0, min(1.0, t / SWELL, (2 * SWELL + PULL_HOLD - t) / SWELL))
        pull.append(pull_g * ease)
    return pull
