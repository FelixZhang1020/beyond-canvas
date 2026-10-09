"""The stack every tool test runs on: eleven boxes in five collections, built by a script."""
import subprocess


def test_the_fixture_builds_eleven_pieces(blender, stack_model):
    done = subprocess.run(
        [str(blender), "-b", str(stack_model), "--python-exit-code", "1", "--python-expr",
         "import bpy; print('OBJECTS', len(bpy.data.objects), sorted(c.name for c in bpy.data.collections))"],
        capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert "OBJECTS 11 ['01_Platform', '02_Columns', '05_Beams', '06_Rafters', '07_Covering']" in done.stdout
