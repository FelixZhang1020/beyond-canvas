"""Load model weights on the GB10 without memory-mapping them.

Measured in the Spark's own container, one 7.8 GB safetensors file
already in the page cache: memory-mapped then copied to the GPU, 48.8 s; read
into ordinary memory then copied, 5.3 s; placed on the GPU by safetensors
itself, 1.0 s. diffusers memory-maps by default, and a whole FLUX.2 Klein took
105 s to place against 3.3 s to then make the picture. The 4090 never showed
this, which is why its workers do not need this file.

diffusers' own models take `disable_mmap=True`; transformers 4.57 has no such
switch, so a text encoder is built from a state dict read here instead.
"""
from pathlib import Path

import torch
from safetensors.torch import load


def read_state(folder: str | Path) -> dict[str, torch.Tensor]:
    """Every safetensors shard in folder, read whole rather than memory-mapped."""
    state: dict[str, torch.Tensor] = {}
    for shard in sorted(Path(folder).glob('*.safetensors')):
        state.update(load(shard.read_bytes()))
    return state


def text_encoder(cls, folder: str | Path, dtype: torch.dtype):
    """A transformers model from its folder, on the GPU, its weights never memory-mapped.

    transformers 4.57 refuses a state dict together with a folder name, so the
    config is read from the folder and the name left out.
    """
    config = cls.config_class.from_pretrained(folder, local_files_only=True)
    model = cls.from_pretrained(None, config=config, state_dict=read_state(folder), torch_dtype=dtype)
    return model.to('cuda')
