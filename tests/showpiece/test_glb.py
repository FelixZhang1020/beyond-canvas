"""The GLB copy of a model for the live 3D view: every piece a node under its own name."""
import json
import struct

from showpiece.blend import SKILLS  # noqa: F401  (the harness's fixtures)

from studio.showpiece import models


def glb_nodes(path):
    data = path.read_bytes()
    magic, _version, _length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF"
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    assert chunk_type == 0x4E4F534A, "the first chunk is JSON"
    return [n.get("name") for n in json.loads(data[20:20 + chunk_length])["nodes"]]


def test_the_stack_exports_with_its_eleven_pieces_named(blender, stack_model, tmp_path):
    target = models.export_glb(stack_model, tmp_path / "models")
    assert target is not None and target.name == "stack.glb" and target.stat().st_size > 1000
    names = glb_nodes(target)
    assert "Column SW" in names and "Tile sheet" in names and "Ridge beam" in names
    assert len(names) == 11
    assert models.is_fresh(stack_model, target), "the copy is newer than the model"
    again = models.export_glb(stack_model, tmp_path / "models")
    assert again == target
