"""Run one image through the configured multi-model TRELLIS.2 classroom route."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from studio.making import glb
from studio.core.images import to_data_uri
from studio.providers import build_media_slot
from studio.core.slots import load_profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    slot = build_media_slot(load_profile("cloud")["mesh.portrait"])
    result = slot.to_mesh(image=to_data_uri(args.image, max_edge=1024), model_choice="trellis2")
    faces = glb.validate(result.content)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result.content)
    print(json.dumps({
        "provider": result.provider,
        "model": result.model,
        "seconds": round(time.monotonic() - started, 3),
        "bytes": len(result.content),
        "triangles": faces,
        "output": str(args.output),
    }))


if __name__ == "__main__":
    main()
