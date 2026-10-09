"""Run Pixal3D on an RGBA input without loading the optional gated matting model."""

import argparse
import os
import tempfile

import cv2
import numpy as np
import torch
from PIL import Image

from pixal3d.pipelines import rembg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--dino-path", required=True)
    parser.add_argument("--fov", type=float, default=0.3490658504)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # Pixal3D only calls BiRefNet for RGB inputs. The smoke-test input already
    # contains a foreground alpha mask, so avoid constructing that optional,
    # gated dependency altogether.
    rembg.BiRefNet = lambda **_: None

    torch_hub_load = torch.hub.load

    def load_cached_naf(repo_or_dir, model, *load_args, **load_kwargs):
        if repo_or_dir == "valeoai/NAF":
            repo_or_dir = os.environ["NAF_REPO_PATH"]
            load_kwargs["source"] = "local"
        return torch_hub_load(repo_or_dir, model, *load_args, **load_kwargs)

    torch.hub.load = load_cached_naf

    import inference

    for config in inference.IMAGE_COND_CONFIGS.values():
        config["model_name"] = args.dino_path

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    image_path = args.image
    image = Image.open(image_path)
    if image.mode != "RGBA" or np.all(np.asarray(image)[..., 3] == 255):
        # The saved bake-off preprocessing uses a solid black backdrop. Remove
        # only near-black regions connected to an image edge, preserving dark
        # marks enclosed by the subject.
        rgb = np.asarray(image.convert("RGB"))
        candidate = np.all(rgb <= 8, axis=2).astype(np.uint8)
        count, labels = cv2.connectedComponents(candidate, connectivity=8)
        edge_labels = np.unique(
            np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
        )
        background = np.isin(labels, edge_labels[edge_labels != 0])
        rgba = np.dstack((rgb, np.where(background, 0, 255).astype(np.uint8)))
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.close()
        Image.fromarray(rgba, "RGBA").save(handle.name)
        image_path = handle.name

    inference.run_inference(
        image_path=image_path,
        output_path=args.output,
        seed=args.seed,
        model_path=args.model_path,
        manual_fov=args.fov,
        # low_vram moves each model onto the card per stage, how the 4090's 24 GB holds it. On
        # the DGX Spark, one memory for both, TRELLIS.2's same move hung jobs, and Pixal3D jobs
        # stalled the same way after a sampling stage; media_spark.py sets
        # PIXAL_LOW_VRAM=0 so all ~18 GB load once. docs/measured/trellis-hang-on-spark.md
        low_vram=os.environ.get("PIXAL_LOW_VRAM", "1") != "0",
        resolution=1024,
    )


if __name__ == "__main__":
    main()
