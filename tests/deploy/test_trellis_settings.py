"""The class's TRELLIS.2 settings are pinned in the worker the GPU machine runs; the seed is one of them."""
from pathlib import Path

WORKER = Path("deploy/gpu-media/extra/trellis_worker.py")


def test_the_class_makes_its_models_with_seed_seven():
    """Seed 42 left three of four geometry sketches hollow or without their ball; seed 7 made all four solid,
    and heads and fruit as well as 42 did (docs/measured/two-routes-for-pencil-sketches.md).
    TRELLIS.2 is the fallback whenever the clean-solids reading cannot answer, so its seed decides what a
    geometry sketch gets then. The worker runs inside its container and cannot be imported here."""
    source = WORKER.read_text()
    assert "seed=7," in source and "seed=42" not in source
