# Wan 2.2 TI2V-5B color I2V smoke test

This smoke test uses the official Wan 2.2 source at commit
`42bf4cfaa384bc21833865abc2f9e6c0e67233dc` and the official
`Wan-AI/Wan2.2-TI2V-5B` checkpoint at revision
`921dbaf3f1674a56f47e83fb80a34bac8a8f203e`.

It generates a short 17-frame, 10-step image-to-video sample from Wan's
included colorful beach/cat input. Model and T5 CPU offloading are enabled for
the 24 GB RTX 4090 D. PyTorch expandable CUDA segments are enabled to reduce
fragmentation during VAE decoding.
