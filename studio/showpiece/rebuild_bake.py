"""Make the replay page's 3D data on the Spark from the recorded, adopted hall build.

Three jobs, all from files the Spark already holds, none of them a new agent run:

- union: the seventeen stage models rebuilt from the logged placement calls (rebuild_demo.py) are
  joined into one GLB. A piece that is the same in two stages is kept once; a piece a repair moved
  is kept once per shape it had. rebuild-hall.json says which pieces stand at each stage, so the
  page shows any stage of the build by hiding the rest.
- tests: for each round the agent tested, the load-path skill's own settle and shake tests are run
  again on that round's model, for as long and at as many frames a second as the run's own call
  asked (its logged command, read from the replay record), and every piece's position is sampled
  every second frame. Positions only: a turn is not kept, and the page says so.
- loads: each round's load colours (flow.json, made by the same skill) are mapped onto the pieces.
- single: an earlier run's own final hall.blend, exported the same way as one stage, so the page can
  show where that run ended; its steps come from its own log, not from a rebuild.
- a design's stages: a design run keeps the hall after every placing call (stages/step-N.blend), so
  its union is made from those, whatever steps they are, and nothing is re-run (rebuild_designs.py).

Usage, on the Spark: python3 -m studio.showpiece.rebuild_bake --work ~/beyond-canvas-demo-work --out DIR
The Blender halves run inside Blender, started by the driver below.
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from array import array
from pathlib import Path

STAGES = [6, 8, 10, 16, 18, 20, 22, 28, 30, 32, 52, 54, 68, 82, 96, 110, 126]
ROUNDS = [32, 54, 68, 82, 96, 110, 126]          # the stages the agent ran its checks on
FAMILIES = ["stone", "columns", "walls", "tie", "brackets", "frame", "purlins", "rafters", "roof_tiles", "ridges"]
EVERY = 2                                        # sample every second frame of the 24 fps bake
UNIT_MM = 0.25                                   # int16 steps: +-8.19 m, finer than the page can show


def family_of(obj) -> str:
    collection = obj.users_collection[0].name.lower() if obj.users_collection else ""
    return next((f for f in FAMILIES if f in collection), "other")


def signature(obj) -> str:
    from mathutils import Vector
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = [round(min(c[i] for c in corners), 3) for i in range(3)]
    hi = [round(max(c[i] for c in corners), 3) for i in range(3)]
    return f"{obj.name}|{len(obj.data.vertices)}|{lo}|{hi}"


def union(stage_dir: Path, out: Path, steps: list[int] = STAGES, name: str = "rebuild-hall.glb") -> None:
    """Inside Blender: read every stage, give each distinct piece an id, append each once, export."""
    import bpy
    pieces, ids, members, first_seen = [], {}, {}, {}
    for step in steps:
        bpy.ops.wm.open_mainfile(filepath=str(stage_dir / f"step-{step}.blend"))
        present = {}
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH":
                continue
            sig = signature(obj)
            if sig not in ids:
                ids[sig] = len(pieces)
                pieces.append([obj.name, family_of(obj)])
                first_seen.setdefault(step, []).append(obj.name)
            present[obj.name] = ids[sig]
        members[f"step-{step}"] = present
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    for step, wanted in first_seen.items():
        with bpy.data.libraries.load(str(stage_dir / f"step-{step}.blend"), link=False) as (_src, dst):
            dst.objects = list(wanted)
        for obj in dst.objects:
            scene.collection.objects.link(obj)
            obj.name = f"p{members[f'step-{step}'][obj.name]:05d}"
    bpy.ops.export_scene.gltf(filepath=str(out / name), export_format="GLB", export_materials="NONE",
                              export_apply=True, export_yup=True, export_texcoords=False)
    (out / "union.json").write_text(json.dumps({"pieces": pieces, "members": members}))
    print(f"UNION {len(pieces)} pieces from {len(steps)} stages", flush=True)


def single(blend: Path, out: Path) -> None:
    """Inside Blender, the run's hall open: every mesh renamed to its id and exported with its family."""
    import bpy
    pieces = []
    for obj in sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name):
        pieces.append([obj.name, family_of(obj)])
        obj.name = f"p{len(pieces) - 1:05d}"
    bpy.ops.export_scene.gltf(filepath=str(out.with_suffix(".glb")), export_format="GLB", export_materials="NONE",
                              export_apply=True, export_yup=True, export_texcoords=False)
    out.with_suffix(".json").write_text(json.dumps({"source": f"the run's own final {blend.name}", "pieces": pieces}))
    print(f"SINGLE {len(pieces)} pieces from {blend}", flush=True)


def shake_protocol(S, frames: int, fps: int) -> dict:
    site = S.SITE
    return {"peak_g": site["peak_g"], "hz": site["hz"], "pull_g": site["pull_g"], "degrees": site["degrees"],
            "source": site["source"], "shaking_seconds": round(S.shaking_seconds(frames, fps), 2),
            "path": S.ground_path(frames, fps, site["peak_g"], site["hz"]),
            "pull": S.sideways_pull(frames, fps, site["pull_g"])}


def sample(scene, tracked: list[str], frames: int) -> array:
    """Every tracked piece's travel from frame 1, in UNIT_MM steps, every EVERY frames and the last."""
    import bpy
    depsgraph = bpy.context.evaluated_depsgraph_get()
    out, first = array("h"), None
    for frame in list(range(1, frames + 1, EVERY)) + ([frames] if (frames - 1) % EVERY else []):
        scene.frame_set(frame)
        now = [scene.objects[n].evaluated_get(depsgraph).matrix_world.translation.copy() for n in tracked]
        first = first or now
        for a, b in zip(first, now):
            out.extend(max(-32767, min(32767, round((b[i] - a[i]) * 1000 / UNIT_MM))) for i in range(3))
    return out


def physics(tag: str, a) -> None:
    """Inside Blender, the stage model already open: settle.py's own build and bake, then sampling."""
    import bpy
    sys.path.insert(0, str(a.scripts))
    import settle as S
    shaking, scene, fps = tag == "shake", bpy.context.scene, a.fps
    roles = {n: p["role"] for n, p in json.loads(a.anatomy.read_text())["pieces"].items()}
    frames = max(2, int(round(a.seconds * fps)))
    pairs = S.block_pairs(json.loads(a.bearing.read_text())["rests_on"])
    shake = shake_protocol(S, frames, fps) if shaking else None
    S.GRIP["friction"] = 1.0 if shaking else S.FRICTION
    names, group_of, _groups, before = S.build(scene, roles, frames, pairs, shake)
    midway = int((S.LEAD + shake["shaking_seconds"] + S.PAUSE / 2) * fps) if shake else None
    moved = S.run(scene, names, group_of, before, frames, midway)
    to_id = json.loads(a.names.read_text())
    ground = [n for n, r in roles.items() if r == "ground"]
    tracked = [n for n in names + ground if n in scene.objects and n in to_id]
    samples = sample(scene, tracked, frames)
    a.target.write_bytes(gzip.compress(samples.tobytes(), 9))
    header = {"ids": [to_id[n] for n in tracked], "frames": frames, "fps": fps, "every": EVERY, "unit_mm": UNIT_MM,
              "samples": len(samples) // (3 * len(tracked)),
              "fell": sum(1 for r in moved.values() if r["moved_m"] > 1.0),
              "shifted": sum(1 for r in moved.values() if 0.10 < r["moved_m"] <= 1.0),
              "max_moved_mm": round(max(r["moved_m"] for r in moved.values()) * 1000, 1),
              "shake": S.shake_summary(shake, moved)[0] if shake else None}
    a.target.with_suffix(".json").write_text(json.dumps(header))
    print(f"{tag.upper()} {len(tracked)} pieces, {header['samples']} samples, fell {header['fell']}", flush=True)


def blender(args: list[str], log: Path, blend: Path | None = None) -> None:
    exe = shutil.which("blender")
    if not exe:
        raise SystemExit("Blender is required")
    cmd = [exe, "-b", *([str(blend)] if blend else []), "--python-exit-code", "1", "--python", __file__, "--", *args]
    with log.open("w") as f:
        subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)


def round_dir(work: Path, step: int) -> Path:
    return work / ("physics-final" if step == 126 else f"load-{step}")


def asked(record: dict) -> dict:
    """How long and at how many frames a second each round's own settle and shake calls ran, from the
    commands the replay record keeps; a flag the call left out takes the load-path skill's default."""
    import re
    found = {}
    for step in record["steps"]:
        if step.get("physics"):
            seconds = re.search(r"--seconds (\S+)", step["command"])
            fps = re.search(r"--fps (\S+)", step["command"])
            found[(step["frame"], step["physics"])] = (float(seconds.group(1)) if seconds else (6.0 if step["physics"] == "shake" else 4.0),
                                                       int(fps.group(1)) if fps else 24)
    return found


def run_round(work: Path, out: Path, scripts: Path, only: set[str], step: int, to_id: dict, settings: dict) -> dict:
    key, folder = f"step-{step}", round_dir(work, step)
    names = out / f"names-{key}.json"
    names.write_text(json.dumps(to_id))
    for tag in ("settle", "shake"):
        if tag in only:
            seconds, fps = settings[(key, tag)]
            blender([tag, "--anatomy", str(folder / "anatomy.json"), "--bearing", str(folder / "bearing.json"),
                     "--names", str(names), "--target", str(out / f"rebuild-{tag}-{key}.gz"), "--scripts", str(scripts),
                     "--seconds", str(seconds), "--fps", str(fps)],
                    out / f"{tag}-{key}.log", work / "output-v2" / f"{key}.blend")
    flow = json.loads((folder / "flow.json").read_text())
    return {"flow_frames": flow["frames"],
            "loads": [[to_id[p["name"]], round(p["carries_N"] / 1000, 2), p["reveal_frame"]]
                      for p in flow["pieces"] if p["name"] in to_id],
            **{tag: json.loads((out / f"rebuild-{tag}-{key}.json").read_text()) for tag in ("settle", "shake")}}


def drive(work: Path, out: Path, scripts: Path, only: set[str], record: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if "union" in only:
        blender(["union", "--stages", str(work / "output-v2"), "--out", str(out)], out / "union.log")
    made = json.loads((out / "union.json").read_text())
    settings = asked(json.loads(record.read_text(encoding="utf-8")))
    rounds = {f"step-{s}": run_round(work, out, scripts, only, s, made["members"][f"step-{s}"], settings) for s in ROUNDS}
    record = {"source": "DGX Spark: stage models rebuilt from the adopted run's logged placements; tests re-run "
                        "with the load-path skill's own settings; positions only, sampled every second frame",
              "scale_kN": [0.5, 1000.0], "families": FAMILIES, "pieces": made["pieces"],
              "stages": {k: sorted(set(v.values())) for k, v in made["members"].items()}, "rounds": rounds}
    (out / "rebuild-hall.json").write_text(json.dumps(record, separators=(",", ":")))
    print(f"wrote {out / 'rebuild-hall.json'}")


def kept_stages(stage_dir: Path, out: Path, stem: str) -> dict:
    """A design's stage models joined into stem.glb and the stages record the page plays, stem.json.
    Every step-N.blend the run kept is a stage; there are no rounds, because nothing is re-run."""
    steps = sorted(int(p.stem.split("-")[1]) for p in stage_dir.glob("step-*.blend"))
    if not steps:
        raise SystemExit(f"{stage_dir} holds no step-N.blend")
    out.mkdir(parents=True, exist_ok=True)
    blender(["union", "--stages", str(stage_dir), "--out", str(out), "--steps", ",".join(map(str, steps)),
             "--name", f"{stem}.glb"], out / "union.log")
    made = json.loads((out / "union.json").read_text())
    record = {"source": "DGX Spark: the stage models the design run kept after each placing call, joined into one",
              "kept_stages": True, "families": FAMILIES, "pieces": made["pieces"],
              "stages": {k: sorted(set(v.values())) for k, v in made["members"].items()}}
    (out / f"{stem}.json").write_text(json.dumps(record, separators=(",", ":")))
    return record


def main() -> None:
    if "--" in sys.argv:                          # inside Blender
        argv = sys.argv[sys.argv.index("--") + 1:]
        parser = argparse.ArgumentParser()
        for flag in ("--stages", "--out", "--anatomy", "--bearing", "--names", "--target", "--scripts", "--blend"):
            parser.add_argument(flag, type=Path)
        parser.add_argument("--seconds", type=float)
        parser.add_argument("--fps", type=int)
        parser.add_argument("--steps", default=",".join(map(str, STAGES)))
        parser.add_argument("--name", default="rebuild-hall.glb")
        a = parser.parse_args(argv[1:])
        if argv[0] == "single":
            single(a.blend, a.out)
        elif argv[0] == "union":
            union(a.stages, a.out, [int(s) for s in a.steps.split(",")], a.name)
        else:
            physics(argv[0], a)
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, help="the Spark folder holding output-v2 and the round folders")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scripts", type=Path, default=Path(__file__).resolve().parents[2] / "skills/load-path/scripts")
    parser.add_argument("--only", default="union,settle,shake", help="which Blender jobs to run; the rest are reused")
    parser.add_argument("--single", type=Path, help="an earlier run's hall.blend: export it alone to --out (a path stem)")
    parser.add_argument("--record", type=Path, default=Path(__file__).resolve().parents[2] / "studio/showpiece/page/rebuild-record.json",
                        help="the replay record, whose logged commands say how long each round's tests ran")
    a = parser.parse_args()
    if a.single:
        blender(["single", "--blend", str(a.single.resolve()), "--out", str(a.out.expanduser().resolve())],
                a.out.expanduser().resolve().with_suffix(".log"), a.single.resolve())
        return
    if not a.work:
        parser.error("--work is needed unless --single is given")
    drive(a.work.expanduser().resolve(), a.out.expanduser().resolve(), a.scripts.resolve(), set(a.only.split(",")),
          a.record.expanduser().resolve())


if __name__ == "__main__":
    main()
