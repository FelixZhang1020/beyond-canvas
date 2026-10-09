"""Pinned FLUX Klein worker; lifetime ends after one bounded GPU job."""
import json
import sys
import torch
from PIL import Image
from diffusers import Flux2KleinPipeline
p = json.load(open('/job/request.json'))
torch.set_num_threads(8)
pipe = Flux2KleinPipeline.from_pretrained('/models/flux', torch_dtype=torch.bfloat16, local_files_only=True)
pipe.enable_model_cpu_offload()
source = Image.open('/job/input.png').convert('RGB')
source.thumbnail((1024, 1024))
width, height = (max(64, n // 16 * 16) for n in source.size)
image = pipe(prompt=p['instruction'], image=source, width=width, height=height,
             num_inference_steps=4, guidance_scale=1.0,
             generator=torch.Generator('cpu').manual_seed(42)).images[0]
image.save('/job/output.png')
