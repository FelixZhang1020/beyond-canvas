"""Wan 2.2 I2V A14B on the Spark: one clip per container, then its memory is freed.

The same model the Mac + 4090 bought from Replicate, made on the Spark. At the
Replicate settings (81 frames at 480p, 30 steps) a clip needs ~31 min on the
GB10 (~190 s to load, ~54.6 s a step), and a class allowed 20. So: 81 frames in
15 steps at 480p by area, seed 42, guidance 3.5, played at 16 fps, Wan's own
rate (~5.1 s on screen) — 1,082 s measured, chosen by the operator
over 3, 7 and 10 s (docs/measured/clip-length-trial.md). 49 frames
(~3 s, 691 s) was the class's length before that.
Both 14B denoisers stay loaded in bf16 beside the text encoder, ~80 GiB in use
while it runs, which the 4090 could never hold. The VAE stays in float32, as
diffusers' own Wan examples load it. No weight file is memory-mapped: fast_load.py
has the measurement, and at 126 GB on disk the memory-mapped path would spend
most of a clip loading.

Reads /job/request.json and /job/input.png, writes /job/output.mp4; the media
server around it checks the clip and answers the studio.
"""
import json

import torch
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
from diffusers.utils import export_to_video
from PIL import Image
from transformers import UMT5EncoderModel

from fast_load import text_encoder

request = json.load(open('/job/request.json'))
vae = AutoencoderKLWan.from_pretrained('/models/wan', subfolder='vae', torch_dtype=torch.float32,
                                       local_files_only=True, disable_mmap=True)
pipe = WanImageToVideoPipeline.from_pretrained(
    '/models/wan', vae=vae, torch_dtype=torch.bfloat16, local_files_only=True, disable_mmap=True,
    text_encoder=text_encoder(UMT5EncoderModel, '/models/wan/text_encoder', torch.bfloat16),
)
pipe.to('cuda')

# 480p by area, keeping the drawing's own shape; both sides must fit the latent grid.
image = Image.open('/job/input.png').convert('RGB')
area, ratio = 480 * 832, image.height / image.width
grid = pipe.vae_scale_factor_spatial * pipe.transformer.config.patch_size[1]
height = round((area * ratio) ** 0.5) // grid * grid
width = round((area / ratio) ** 0.5) // grid * grid

# 42 unless the studio asks for another start: it does for a new try after a clip it held back
# (hands or brushes Wan painted in), which with the same start would come out the same.
seed = request.get('seed', 42)
if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2 ** 31:
    seed = 42
# 81 pictures (~5 s at 16 fps, the most Wan 2.2 was trained on) unless asked otherwise. The class
# never asks; the length trial (clip_length_trial.py) does. Wan's frame counts are 4k+1; 161 is 10 s.
count = request.get('frames', 81)
if isinstance(count, bool) or not isinstance(count, int) or not 17 <= count <= 161 or count % 4 != 1:
    count = 81
frames = pipe(image=image.resize((width, height)), prompt=request['instruction'],
              height=height, width=width, num_frames=count, num_inference_steps=15,
              guidance_scale=3.5, generator=torch.Generator('cuda').manual_seed(seed)).frames[0]
export_to_video(frames, '/job/output.mp4', fps=16)
