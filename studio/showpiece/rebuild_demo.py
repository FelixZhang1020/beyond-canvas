"""Recreate stills for the recorded, adopted hall build on the Spark.

The input is a small, checked-in transcript of successful placement calls. This
replays those calls in a separate output folder, then renders fixed-camera stills
from the saved stages. It does not rerun the agent or claim these are frames that
were captured during the original run.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def make_stages(out: Path, record: dict, root: Path) -> None:
    from studio.showpiece.catalog import TOOLS, argv_for

    source = root / "output/foguang-east-hall/foguang-east-hall-v25.blend"
    if not source.is_file():
        raise SystemExit(f"missing reference model: {source}")
    out.mkdir(parents=True, exist_ok=True)
    hall = out / "hall.blend"
    if hall.exists():
        raise SystemExit(f"output already contains a hall; use a fresh replay directory: {hall}")
    survey = argv_for(TOOLS["hall-carpenter", "survey"], {}, source, out)
    with (out / "survey.log").open("w") as log:
        subprocess.run(survey, cwd=root, check=True, stdout=log, stderr=subprocess.STDOUT)
    wanted = {chapter["frame"] for chapter in record["chapters"] if chapter["frame"].startswith("step-")}
    made: set[str] = set()
    for action in record["placements"]:
        step = action["step"]
        spec = TOOLS["hall-carpenter", action["tool"]]
        cmd = argv_for(spec, action["args"], None, out, hall)
        with (out / f"place-{step}.log").open("w") as log:
            subprocess.run(cmd, cwd=root, check=True, stdout=log, stderr=subprocess.STDOUT)
        key = f"step-{step}"
        if key in wanted:
            shutil.copy2(hall, out / f"{key}.blend")
            made.add(key)
            print(f"saved {key}", flush=True)
    missing = wanted - made
    if missing:
        raise SystemExit(f"missing checkpoints: {sorted(missing)}")


def render(out: Path, record: dict, root: Path) -> None:
    # This branch runs inside Blender. Each snapshot is opened afresh so lights
    # and cameras from the preceding render cannot leak into the next one.
    import bpy
    from mathutils import Vector

    sys.path.insert(0, str(root / "skills/hall-carpenter/scripts"))
    from shadow import lit_view
    from set_scene import render_still

    # The build tools only create geometry. Give the re-rendered stills a clear
    # visual material key without changing any saved stage or the historical run.
    palette = {
        "stone": (0.53, 0.51, 0.47),
        "columns": (0.33, 0.16, 0.09),
        "walls": (0.66, 0.56, 0.43),
        "tie": (0.35, 0.18, 0.10),
        "brackets": (0.40, 0.20, 0.11),
        "frame": (0.36, 0.18, 0.10),
        "purlins": (0.37, 0.19, 0.10),
        "rafters": (0.43, 0.26, 0.15),
        "roof_tiles": (0.25, 0.27, 0.29),
        "ridges": (0.19, 0.20, 0.22),
    }

    box = record["frame_box"]
    lo, hi = Vector(box[0]), Vector(box[1])
    frames = ["temple", *dict.fromkeys(ch["frame"] for ch in record["chapters"] if ch["frame"] != "temple")]
    for frame in frames:
        if frame == "temple":
            continue  # survey.py already rendered the real reference model.
        bpy.ops.wm.open_mainfile(filepath=str(out / f"{frame}.blend"))
        materials = {}
        object_roles = {}
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH":
                continue
            collection = obj.users_collection[0].name.lower()
            role = next((name for name in palette if name in collection), None)
            if role is None:
                continue
            object_roles[obj.name] = role
            if role not in materials:
                material = bpy.data.materials.new(f"Demo {role}")
                material.use_nodes = True
                material.diffuse_color = (*palette[role], 1)
                material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*palette[role], 1)
                material.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.82
                materials[role] = material
            obj.data.materials.clear()
            obj.data.materials.append(materials[role])
        lit_view(bpy.context.scene, lo, hi, str(out / f"{frame}.png"), 1280, 720)
        print(f"rendered {frame}", flush=True)
        if frame == "step-32":
            # The same camera and colours make each actual component family a
            # transparent overlay. The browser raises these in construction
            # order; it does not invent geometry between recorded placements.
            scene = bpy.context.scene
            scene.render.film_transparent = True
            scene.render.image_settings.color_mode = "RGBA"
            for layer in record["layers"]:
                for obj in scene.objects:
                    if obj.type == "MESH":
                        obj.hide_render = object_roles.get(obj.name) != layer["role"]
                render_still(scene, str(out / f"rebuild-layer-{layer['role']}.png"))
                print(f"rendered layer {layer['role']}", flush=True)
        if frame in record["cutaway_frames"]:
            # The exterior roof hides changes to end-beam counts. A second
            # view keeps the camera fixed while temporarily hiding the roof,
            # purlins and rafters so each logged frame replacement is visible.
            scene = bpy.context.scene
            for obj in scene.objects:
                if obj.type == "MESH":
                    obj.hide_render = object_roles.get(obj.name) in {"roof_tiles", "ridges", "rafters", "purlins"}
            render_still(scene, str(out / f"cutaway-{frame}.png"))
            print(f"rendered cutaway {frame}", flush=True)


def compress(out: Path, record: dict) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to encode the web stills")
    # The Spark ffmpeg wrapper only mounts /tmp into its container.
    with tempfile.TemporaryDirectory(prefix="rebuild-demo-") as temp:
        for frame in dict.fromkeys(ch["frame"] for ch in record["chapters"]):
            source = out / ("temple.png" if frame == "temple" else f"{frame}.png")
            inside = Path(temp) / "source.png"
            encoded = Path(temp) / "still.jpg"
            shutil.copy2(source, inside)
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(inside), "-q:v", "3", str(encoded)], check=True)
            target = out / f"rebuild-{frame}.jpg"
            shutil.copy2(encoded, target)
            print(f"encoded {target.name} ({target.stat().st_size} bytes)", flush=True)
        for layer in record["layers"]:
            source = out / f"rebuild-layer-{layer['role']}.png"
            inside = Path(temp) / "source.png"
            encoded = Path(temp) / "layer.webp"
            shutil.copy2(source, inside)
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(inside),
                            "-c:v", "libwebp", "-q:v", "86", "-compression_level", "6",
                            "-pix_fmt", "yuva420p", str(encoded)], check=True)
            target = out / f"rebuild-layer-{layer['role']}.webp"
            shutil.copy2(encoded, target)
            print(f"encoded {target.name} ({target.stat().st_size} bytes)", flush=True)
        for frame in record["cutaway_frames"]:
            inside = Path(temp) / "source.png"
            encoded = Path(temp) / "still.jpg"
            shutil.copy2(out / f"cutaway-{frame}.png", inside)
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(inside), "-q:v", "3", str(encoded)], check=True)
            target = out / f"rebuild-cutaway-{frame}.jpg"
            shutil.copy2(encoded, target)
            print(f"encoded {target.name} ({target.stat().st_size} bytes)", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--record", type=Path)
    parser.add_argument("--render", action="store_true", help="internal Blender stage")
    parser.add_argument("--compress-only", action="store_true", help="encode existing stills without rebuilding")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    root = args.root.resolve()
    sys.path.insert(0, str(root))
    record_path = (args.record or root / "studio/showpiece/page/rebuild-record.json").resolve()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    out = args.out.resolve()
    if args.render:
        render(out, record, root)
        return
    if args.compress_only:
        compress(out, record)
        return
    make_stages(out, record, root)
    blender = shutil.which("blender")
    if not blender:
        raise SystemExit("Blender is required")
    with (out / "render.log").open("w") as log:
        subprocess.run([blender, "-b", "--python-exit-code", "1", "--python", str(Path(__file__)), "--", "--out", str(out), "--root", str(root), "--record", str(record_path), "--render"], cwd=root, check=True, stdout=log, stderr=subprocess.STDOUT)
    compress(out, record)


if __name__ == "__main__":
    main()
