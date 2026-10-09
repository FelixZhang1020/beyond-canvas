"""Shared by the showpiece tests: a Blender to run tools in, and a small stack to run them on.

Where there is no Blender (a CI runner, a laptop without it) the tool tests skip and say why;
the packaging and judge tests still run everywhere.
"""
from pathlib import Path

import pytest
from showpiece.blend import SKILLS, find_blender, run_in_blender


@pytest.fixture(autouse=True)
def a_blender_path_where_there_is_none(monkeypatch):
    """Tests that only build a Blender command, or hand it to a stand-in runner, need a path, not Blender.

    Found when the suites moved to the Spark before it had a Blender: eight such
    tests had passed only because the Mac has Blender installed. Where the studio finds none, they
    get a path that is never run; tests that do run Blender use `blender` below and skip. The Spark
    has one now (deploy/spark/bin/blender), so there all of them run.
    A machine with Blender is untouched, and a test that patches its own answer still wins.
    """
    from studio.showpiece import blender_bin, catalog
    if blender_bin.find_blender() is None:
        stand_in = Path("/no-blender-here/blender")
        monkeypatch.setattr(blender_bin, "find_blender", lambda: stand_in)
        monkeypatch.setattr(catalog, "find_blender", lambda: stand_in)


@pytest.fixture(scope="session")
def blender() -> Path:
    found = find_blender()
    if found is None:
        pytest.skip("no Blender binary: set BLENDER_BIN or install Blender")
    assert found is not None
    return found


@pytest.fixture(scope="session")
def stack_model(blender, tmp_path_factory) -> Path:
    """The eleven-piece stack every tool test runs on, built once per session."""
    out = tmp_path_factory.mktemp("stack") / "stack.blend"
    run_in_blender(blender, None, SKILLS / "model-anatomy/scripts/fixture.py", str(out))
    assert out.is_file()
    return out
