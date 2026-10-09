"""TRELLIS.2 on the private 4090, with explicit Pixal3D cloud selection."""
from __future__ import annotations

from studio.core.errors import ModelRefused
from studio.providers.cloudmesh import CloudMeshClient
from studio.providers.localmesh import LocalMeshClient


class HybridMeshClient:
    """Route the default model locally without removing the manual cloud backup."""

    def __init__(self, model, options=None, *, local=None, cloud=None):
        self.model, self.options = model, dict(options or {})
        self.local = local or LocalMeshClient("trellis2", self.options)
        self.cloud = cloud or CloudMeshClient("pixal", self.options)

    def make(self, inputs):
        choice = inputs.get("model_choice", "trellis2")
        if choice == "trellis2":
            return self.local.make(inputs)
        if choice == "pixal":
            return self.cloud.make(inputs)
        raise ModelRefused("Invalid image or model choice")
