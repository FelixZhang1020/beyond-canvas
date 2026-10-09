import json
import torch
from PIL import Image
from inference import ImageGenerator
p = json.load(open('/job/request.json'))
torch.set_num_threads(8)
model = ImageGenerator(ae_path='/models/step1x/vae.safetensors',
    dit_path='/models/step1x/step1x-edit-i1258.safetensors',
    qwen2vl_model_path='/models/step1x/Qwen2.5-VL-7B-Instruct',
    quantized=True, offload=True, version='v1.0')
image = model.generate_image(p['instruction'], negative_prompt='',
    ref_images=Image.open('/job/input.png').convert('RGB'), num_samples=1,
    num_steps=28, cfg_guidance=6, seed=42, show_progress=False, size_level=512)[0]
image.save('/job/output.png')
