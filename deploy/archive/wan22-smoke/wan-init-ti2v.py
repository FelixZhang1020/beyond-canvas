"""TI2V-only package exports for the 4090 smoke-test image.

The upstream package imports speech and animation stacks eagerly. Those optional
paths bring in dependencies that are unrelated to TI2V generation, so this
runtime image exposes only the official TI2V implementation used by the test.
"""

from . import configs, distributed, modules
from .textimage2video import WanTI2V

__all__ = ["WanTI2V", "configs", "distributed", "modules"]
