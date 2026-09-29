"""The joints film explode.py --closeups makes: where the joints are, then each one close, coming apart
and locking again, in Blender's plain look with a caption naming it.

The first version filmed each joint alone on black and made no sense to the operator: a
plate with a hole floated off the top of the picture, a cube sat on a disc, and nothing said what or
where they were. So the film opens on the bracket set in its hall with its three joints marked; then,
for each joint, the camera moves in on its two pieces (one orange, one blue, everything else a ghost),
framed over their whole motion so nothing leaves the picture. The piece that lifts takes the rest of its
block with it (a big block's foot, seat and ears are one block), holds open while the camera turns a
little, and drops back in. Everything happens on the copy in memory; the model file is never saved.
"""
import math
import os

from mathutils import Vector

from set_scene import GHOST, ROLE_TINT, captions, orbit, place_camera, render_frames, render_still

LIFTED, HELD = (0.93, 0.52, 0.18), (0.27, 0.52, 0.80)   # the piece that comes off, the piece it fits into
GAP = 0.45            # a lifted piece clears the one it fits by this much, or the lift hides the joint
ESTABLISH_S = 3.0     # the bracket set in its hall, its joints marked, before the first close-up
NEAR = 8.0            # metres around the set that stay in the picture; farther pieces are not drawn
REACH = 1.0           # a column or a long beam is framed only this far from where the joint is
FAINT = 0.05          # how solid everything but the joint's two pieces is drawn in a close-up
# Where each joint is seen from, (degrees around, degrees up): the tenon low, so it shows standing on the
# column under the block; crossing arms nearly level from between them, where the upper arm's notch
# underneath and the lower arm's on top show as two gaps that fit; a dovetail steeply from the front, the
# beam across the picture, its flared end over the slot it drops into.
VIEWS = {"tenon": (-55, 14), "crosslap": (-45, 6), "dovetail": (-90, 55)}
TURN = 25.0           # degrees the camera turns round a joint while it is held open
FIT = {"tenon": 1.7, "crosslap": 1.0, "dovetail": 1.35}   # how much room round a joint: a tenon's block lifts high
CLEAR = 1.2           # metres round the line from the camera to a joint in which nothing else is drawn
NEAR_LENS = 3.2       # nor anything this close to the camera: a faint piece still draws its full outline
CONTEXT = 2.5         # in a close-up only the pieces this near the joint stay, faint: seen along the eave,
                      # a whole row of faint bracket sets added up to a dark band across the top
# The share of a joint's time at which: the camera has arrived, it is open, it starts to close, it is shut.
ARRIVE, OPENED, CLOSING, SHUT = 0.18, 0.40, 0.72, 0.92


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(t, 0.0), 1.0))


def meeting_point(names, pieces):
    """Where the pieces of a joint meet: the middle of the overlap of their boxes."""
    lo = Vector([max(pieces[n]["box"][0][i] for n in names) for i in range(3)])
    hi = Vector([min(pieces[n]["box"][1][i] for n in names) for i in range(3)])
    return (lo + hi) / 2


def clear_lift(name, joint, pieces):
    """The joint's own lift for this piece, raised until the piece's bottom is GAP above the others:
    a dovetail's lift brings the beam just level with its column's top, over the slot it was to show."""
    d = Vector(joint["explode"][name])
    others = [n for n in joint["pieces"] if n != name and n in pieces]
    if not others or abs(d.z) < 1e-6:
        return d
    top = max(pieces[n]["box"][1][2] for n in others)
    return Vector((d.x, d.y, max(d.z, top + GAP - pieces[name]["box"][0][2])))


def block_of(name):
    """The block a foot, seat or ear belongs to, whether or not a joint was cut into it; else None."""
    head, _, part = name.removesuffix(" | JOINT").rpartition(" ")
    return head if part.split(".")[0] in {"foot", "seat", "ear"} and head.lower().endswith("dou") else None


def opened(t):
    """How far open a joint is at t, its share of its own time: shut, opening, held, closing, shut."""
    if t <= ARRIVE:
        return 0.0
    if t <= OPENED:
        return ease((t - ARRIVE) / (OPENED - ARRIVE))
    return 1.0 if t <= CLOSING else ease((SHUT - t) / (SHUT - CLOSING))


def framing(names, lifts, pieces, meet, fit):
    """Where the camera looks and how far it stands to take in the joint's pieces, lifted and shut;
    a column or a long beam counts only near the joint, or the joint would be a dot."""
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for n in names:
        a, b = (Vector(v) for v in pieces[n]["box"])
        a = Vector([max(a[i], meet[i] - REACH) for i in range(3)])
        b = Vector([min(b[i], meet[i] + REACH) for i in range(3)])
        up = lifts.get(n, Vector())
        for c in (a, b, a + up, b + up):
            lo = Vector([min(lo[i], c[i]) for i in range(3)])
            hi = Vector([max(hi[i], c[i]) for i in range(3)])
    radius = max((hi - lo).length / 2, 0.4)
    return (lo + hi) / 2, radius / math.tan(math.radians(16.0)) * fit   # a 35 mm lens sees 16 degrees up and down


def tint(obj, colour, alpha, frame):
    obj.color = (*colour, alpha)
    obj.keyframe_insert("color", frame=frame)


def near_the_set(scene, pieces, centre):
    """The objects drawn: every piece within NEAR of the set; nothing farther is in the picture."""
    shown = []
    for obj in scene.objects:
        if obj.type not in {"MESH", "CURVE"} or obj.hide_render:
            continue
        piece = pieces.get(obj.name)            # only the hall's own pieces, and not the roof, which takes no part
        roof = piece is not None and piece["role"] in ("covering", "rafter")
        if piece is not None and not roof and (Vector(piece["centre"]) - centre).length <= NEAR:
            shown.append(obj)
        else:
            obj.hide_render = True
    return shown


def own(obj, pieces):
    role = pieces.get(obj.name, {}).get("role")
    return ROLE_TINT.get(role, (0.82, 0.79, 0.73)), GHOST if role in ("covering", "rafter") else 1.0


def lifts_of(joint, names, pieces, scene):
    """How far each lifted piece rises, the rest of its block rising with it."""
    lifts = {n: clear_lift(n, joint, pieces) for n, d in joint["explode"].items() if n in names and Vector(d).length > 1e-6}
    for n in list(lifts):
        stem = block_of(n)
        for mate in (m for m in pieces if stem and block_of(m) == stem and m not in lifts and m in scene.objects):
            lifts[mate] = lifts[n]
    return lifts


def in_the_way(obj, pieces, ats, look):
    """Whether a piece stands between the camera, at any of its places, and the joint, or so near the lens
    that its outline streaks across the picture (a bracket arm 2.7 m from a low camera did)."""
    where = Vector(pieces[obj.name]["centre"]) if obj.name in pieces else obj.matrix_world.translation
    if obj.name in pieces:
        lo, hi = (Vector(v) for v in pieces[obj.name]["box"])
        if any((Vector([min(max(at[i], lo[i]), hi[i]) for i in range(3)]) - at).length < NEAR_LENS for at in ats):
            return True
    for at in ats:
        line = look - at
        t = (where - at).dot(line) / max(line.length_squared, 1e-9)
        if 0.0 < t < 0.9 and (at + line * t - where).length < CLEAR:
            return True
    return False


def hide_between(obj, first, last):
    for frame, hidden in ((first - 1, False), (first, True), (last, True), (last + 1, False)):
        obj.hide_render = hidden
        obj.keyframe_insert("hide_render", frame=frame)


def move(scene, lifts, first, last):
    for n, d in lifts.items():
        obj = scene.objects[n]
        home = obj.matrix_world.translation.copy()
        for f in range(first, last + 1):
            obj.matrix_world.translation = home + d * opened((f - first) / max(last - first, 1))
            obj.keyframe_insert("location", frame=f)
        obj.matrix_world.translation = home


def film(scene, joints, pieces, per_joint, fps, out_dir, words):
    """The whole film into out_dir/explode; each joint's shot, with the still written of it held open."""
    subjects = {n for j in joints for n in j["pieces"] if n in pieces}
    centre = sum((Vector(pieces[n]["centre"]) for n in subjects), Vector()) / max(len(subjects), 1)
    shown = near_the_set(scene, pieces, centre)
    for obj in shown:                                  # the set in its hall, its joints' pieces marked
        colour, alpha = own(obj, pieces)
        tint(obj, LIFTED if obj.name in subjects else colour, alpha, 1)
    establish = int(ESTABLISH_S * fps)
    set_at = orbit(centre, 6.5, 2.5, -55)
    camera = place_camera(scene, set_at, centre, 35.0, focus=False)
    views, lines, shots = [(1, set_at, centre), (establish, set_at, centre)], [(words["set"], 1, establish)], []
    for k, joint in enumerate(joints):
        first = establish + k * per_joint + 1
        last, marked = first + per_joint - 1, first + int(0.12 * per_joint)
        names = [n for n in joint["pieces"] if n in pieces and n in scene.objects]
        lifts = lifts_of(joint, names, pieces, scene)
        for obj in shown:                              # this joint's two pieces in colour, the rest a ghost
            tint(obj, obj.color[:3], obj.color[3], first)
            colour, _ = own(obj, pieces)
            tint(obj, *((LIFTED, 1.0) if obj.name in lifts else (HELD, 1.0) if obj.name in names else (colour, FAINT)),
                 marked)
        move(scene, lifts, first, last)
        look, away = framing(set(names) | set(lifts), lifts, pieces, meeting_point(names, pieces), FIT.get(joint["kind"], 1.4))
        around, up = VIEWS.get(joint["kind"], (-55, 30))
        ats = []
        for share, turn in ((ARRIVE, 0.0), (OPENED, 0.0), (CLOSING, TURN), (1.0, TURN)):
            at = orbit(look, away * math.cos(math.radians(up)), away * math.sin(math.radians(up)), around + turn)
            views.append((first + int(share * (per_joint - 1)), at, look))
            ats.append(at)
        meet = meeting_point(names, pieces)
        for obj in shown:                              # the joint's surroundings only, and nothing in the way
            if obj.name in lifts or obj.name in names:
                continue
            far = (Vector(pieces[obj.name]["centre"]) - meet).length > CONTEXT
            if far or in_the_way(obj, pieces, ats, look):
                hide_between(obj, first + int(ARRIVE * (per_joint - 1)), last)
        lines.append((words[joint["kind"]], first, last))
        shots.append({"kind": joint["kind"], "pieces": names, "frames": [first, last],
                      "held": first + int((OPENED + CLOSING) / 2 * (per_joint - 1))})
    for frame, at, look in views:
        camera.location = at
        camera.rotation_euler = (look - at).to_track_quat("-Z", "Y").to_euler()
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)
    captions(scene, camera, lines)
    end = establish + len(joints) * per_joint
    scene.frame_start, scene.frame_end = 1, end
    for shot in shots:
        scene.frame_set(shot.pop("held"))
        shot["still"] = os.path.basename(render_still(scene, os.path.join(out_dir, f"joint-{shot['kind']}.png")))
    render_frames(scene, os.path.join(out_dir, "explode"), 1, end)
    return shots, end
