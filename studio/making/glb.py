"""Bounded GLB archive boundary. Inspect metadata, never decode meshes or textures."""
import base64
import hashlib
import json
import struct

MAX_BYTES = 16 * 1024 * 1024
MAX_FACES = 350000


def validate(content):
    if not 20 <= len(content) <= MAX_BYTES:
        raise ValueError('GLB size outside budget')
    magic, version, size, count, kind = struct.unpack_from('<5I', content)
    if (magic, version, size, kind) != (0x46546C67, 2, len(content), 0x4E4F534A) or count > 2 * 1024 * 1024 or count + 20 > size:
        raise ValueError('Invalid GLB container')
    data = json.loads(content[20:20+count])
    if any(x.get('uri') for key in ('buffers', 'images') for x in data.get(key, [])):
        raise ValueError('External GLB resources are not supported')
    # Compressed geometry would require extra decoders and defeat the metadata budget.
    if set(data.get('extensionsRequired', [])) - {'EXT_texture_webp'}:
        raise ValueError('Unsupported required GLB extensions')
    faces = 0
    accessors = data.get('accessors', [])
    if any(type(a.get('count')) is not int or not 0 <= a['count'] <= 1050000 or a.get('sparse') for a in accessors):
        raise ValueError('Accessor allocation budget exceeded')
    if sum(a['count'] for a in accessors) > 4000000:
        raise ValueError('Aggregate accessor budget exceeded')
    for view in data.get('bufferViews', []):
        length, offset = view.get('byteLength'), view.get('byteOffset', 0)
        if type(length) is not int or type(offset) is not int or min(length, offset) < 0 or length + offset > len(content):
            raise ValueError('Invalid buffer view')
    meshes = data.get('meshes', [])
    if len(data.get('nodes', [])) > 128 or len(meshes) > 64:
        raise ValueError('GLB object budget exceeded')
    for mesh in meshes:
        for primitive in mesh.get('primitives', []):
            if primitive.get('mode', 4) != 4:
                raise ValueError('GLB must contain triangles')
            index = primitive.get('indices', primitive.get('attributes', {}).get('POSITION'))
            if type(index) is not int or not 0 <= index < len(accessors):
                raise ValueError('Invalid GLB accessor')
            n = accessors[index].get('count')
            if type(n) is not int or n <= 0 or n % 3:
                raise ValueError('Invalid triangle count')
            faces += n // 3
    if not 1 <= faces <= MAX_FACES:
        raise ValueError('GLB face budget exceeded')
    if len(data.get('nodes', [])) and sum('mesh' in n for n in data['nodes']) > len(meshes):
        raise ValueError('Instanced GLB meshes are not supported')
    return faces


def scene(content, aspect, model):
    faces = validate(content)
    return {'version': 1, 'method': 'cloud-glb', 'source_aspect': aspect,
            'model': model, 'bytes': len(content), 'triangles': faces,
            'sha256': hashlib.sha256(content).hexdigest(),
            'glb': base64.b64encode(content).decode('ascii')}
