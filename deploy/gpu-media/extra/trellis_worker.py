"""Single-job TRELLIS.2 inference using the already pinned classroom parameters.

Loading and building are separate, so the Spark can keep the model loaded between
jobs (deploy/spark/trellis_resident.py) instead of paying about 40% of every job to load it again.
Run as a script it does what it always did: load, build /job, exit.
"""
import faulthandler
import os
import sys
sys.path.insert(0, '/app')
import torch
from PIL import Image
import o_voxel
from trellis2.pipelines import Trellis2ImageTo3DPipeline


def load():
    """The pipeline, on the chip, ready for jobs."""
    torch.set_num_threads(8)
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained('/models/runtime/trellis2')
    # low_vram moves each model onto the card for its stage and back afterwards, which is how
    # the 4090's 24 GB holds TRELLIS.2. The DGX Spark has one memory for both, so the moves
    # save nothing, and there a job queued behind a picture job hung inside the move back
    # (flow_model.cpu(), one core spinning, chip idle) — twice in one evening.
    # media_spark.py sets TRELLIS_LOW_VRAM=0: the same order then finished in 243 s
    # with about 4 GiB more memory held. docs/measured/trellis-hang-on-spark.md
    pipeline.low_vram = os.environ.get('TRELLIS_LOW_VRAM', '1') != '0'
    pipeline.cuda()
    return pipeline


def build(pipeline, job='/job'):
    """One drawing in that job folder into one output.glb beside it."""
    image = Image.open(f'{job}/input.png').convert('RGBA')
    image = pipeline.preprocess_image(image)
    # Seed 7, not 42: seed 42 left three of four geometry sketches hollow or without their ball,
    # seed 7 made all four solid and the heads and fruit as well as 42.
    # docs/measured/two-routes-for-pencil-sketches.md
    # The seed is not repeatability: as measured, the same sketch built four times on this node gave
    # four different files (2.97 to 3.16 MB), whether the model had just loaded or was kept between jobs. The
    # chip's own arithmetic decides the rest, so a child who asks twice gets two models, alike but not equal.
    outputs, latents = pipeline.run(image, seed=7, preprocess_image=False,
        sparse_structure_sampler_params={'steps':12,'guidance_strength':7.5,'guidance_rescale':.7,'rescale_t':5.0},
        shape_slat_sampler_params={'steps':12,'guidance_strength':7.5,'guidance_rescale':.5,'rescale_t':3.0},
        tex_slat_sampler_params={'steps':12,'guidance_strength':1.0,'guidance_rescale':0.0,'rescale_t':3.0},
        pipeline_type='1024_cascade',return_latent=True)
    mesh=outputs[0]
    glb=o_voxel.postprocess.to_glb(vertices=mesh.vertices,faces=mesh.faces,
        attr_volume=mesh.attrs,coords=mesh.coords,attr_layout=pipeline.pbr_attr_layout,
        grid_size=latents[2],aabb=[[-.5,-.5,-.5],[.5,.5,.5]],decimation_target=100000,
        texture_size=1024,remesh=True,remesh_band=1,remesh_project=0,use_tqdm=True)
    glb.export(f'{job}/output.glb',extension_webp=True)


if __name__ == '__main__':
    # Every 4 minutes a still-running job writes where each thread is into its log. A normal
    # job ends in about 4.5 min and prints one; it is what located the Spark hang above.
    faulthandler.dump_traceback_later(240, repeat=True)
    build(load())
