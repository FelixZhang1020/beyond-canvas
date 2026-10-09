"""Download public model assets once; inference itself has no download path."""
import argparse
import os
from pathlib import Path

from studio.portrait_runtime.server import WEIGHT_REVISION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(root / "hf-cache")
    os.environ["U2NET_HOME"] = str(root / "masks")
    os.environ.setdefault("OMP_NUM_THREADS", "6")
    from huggingface_hub import snapshot_download
    from rembg import new_session
    weights = root / "weights"
    snapshot_download("VAST-AI/TripoSG", revision=WEIGHT_REVISION, local_dir=weights,
                      allow_patterns=["*.json", "*.safetensors"], max_workers=2)
    (weights / "revision.txt").write_text(WEIGHT_REVISION + "\n")
    new_session("u2net", providers=["CPUExecutionProvider"])
    print("Portrait weights and foreground mask are ready.")


if __name__ == "__main__":
    main()
