"""The arithmetic the survey does on a temple's rafters, free of Blender so it runs in milliseconds.

The fourth live rebuild was told "rafters 0.36 m thick, 0.05 m apart", which cannot be, asked for it,
was refused, and took the placing tool's minimum: 2,684 thick rafters and a column at four fifths of
its strength. The Foguang hall's rafters lie in several tiers, one above the other, and fan out
toward the corners; read as one row, two tiers 5 cm out of step look like rafters 5 cm apart, and a
fanned rafter's box is wider than the rafter.
"""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills/hall-carpenter/scripts/measures.py"


@pytest.fixture(scope="module")
def measures():
    spec = importlib.util.spec_from_file_location("carpenter_measures", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fanned_tier(foot_z, side_y, shift=0.0, count=29, apart=0.40, thickness=0.18):
    """One tier on one slope: centres `apart` apart, each box wider the further it fans from the middle."""
    middle = count // 2
    return [{"x": round((k - middle) * apart + shift, 3), "width": round(thickness + 0.045 * abs(k - middle), 3),
             "y": side_y, "foot": foot_z} for k in range(count)]


def test_tiers_out_of_step_and_fanned_rafters_still_give_the_real_size_and_spacing(measures):
    runs = (fanned_tier(9.39, -11.0) + fanned_tier(9.82, -9.0, shift=0.05) + fanned_tier(10.51, -7.0, shift=0.09)
            + fanned_tier(9.39, 11.0) + fanned_tier(9.82, 9.0, shift=0.05))
    assert measures.rafters(runs) == {"size": 0.18, "spacing": 0.40}


def test_one_straight_row_reads_as_it_always_did(measures):
    runs = [{"x": round(-4 + 0.8 * k, 2), "width": 0.14, "y": -3.0, "foot": 5.0} for k in range(11)]
    assert measures.rafters(runs) == {"size": 0.14, "spacing": 0.8}


def test_fewer_than_three_rafters_is_no_rafters(measures):
    assert measures.rafters(fanned_tier(9.4, -11.0, count=2)) is None


def test_the_remedy_for_timber_through_the_roof_is_only_given_for_the_frames_it_mends(measures):
    """Naming every end line mends a frame's post. It does nothing for a purlin, and a remedy that cannot
    work costs a repair lap: found when the true rafter size let purlin ends show through the covering."""
    posts = measures.through_the_roof_sentence(["Frame -12.49 | king post", "Frame 12.49 | king post"])
    assert posts.startswith("2 timber pieces stand out through the roof: Frame -12.49 | king post")
    assert "end-lines" in posts and "in one call" in posts
    purlins = measures.through_the_roof_sentence(["Purlin ring 1 | end x-", "Purlin ring 1 | end x+"])
    assert purlins.startswith("2 timber pieces stand out through the roof: Purlin ring 1") and "end-lines" not in purlins
    assert "rafters" in purlins, "what the builder can change here is how thick the rafters are"
