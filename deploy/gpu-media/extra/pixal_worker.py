"""Use the verified Pixal runner with classroom-sized GLB export parameters."""
import sys
sys.path.insert(0, "/opt/pixal3d")
import o_voxel
original = o_voxel.postprocess.to_glb

def classroom_glb(*args, **kwargs):
    kwargs['decimation_target'] = 100000
    kwargs['texture_size'] = 1024
    return original(*args, **kwargs)

o_voxel.postprocess.to_glb = classroom_glb
# Classroom uploads may be opaque RGB drawings. Reuse the already pinned
# TRELLIS background-removal weights before the RGBA-only Pixal smoke runner.
import gc
import numpy as np
import torch
from PIL import Image
from pixal3d.pipelines.rembg import BiRefNet
image_index = sys.argv.index('--image') + 1
image = Image.open(sys.argv[image_index]).convert('RGBA')
if np.all(np.asarray(image)[..., 3] == 255):
    remover = BiRefNet(model_name='/models/huggingface/hub/models--briaai--RMBG-2.0/snapshots/5df4c9c76d8170882c34f6986e848ee07fd0ba43')
    remover.cuda()
    image = remover(image.convert('RGB'))
    image.save('/job/input-matted.png')
    sys.argv[image_index] = '/job/input-matted.png'
    remover.cpu()
    del remover
    gc.collect()
    torch.cuda.empty_cache()
from smoke_rgba import main
main()
