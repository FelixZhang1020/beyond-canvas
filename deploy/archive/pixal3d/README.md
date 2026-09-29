# Pixal3D 4090 smoke test

This overlay reuses the pinned TRELLIS.2 CUDA image and adds the official
Pixal3D dependencies. The smoke runner accepts an already-matted RGBA image,
so it does not load Pixal3D's optional gated RMBG-2.0 preprocessing model.

The test runs the official 1024 cascade in low-VRAM mode on a single RTX 4090.
