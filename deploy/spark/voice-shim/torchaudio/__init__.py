"""A stand-in so VoxCPM's package imports on the Spark, where NVIDIA's PyTorch comes without torchaudio.

VoxCPM imports torchaudio at the top of its VoxCPM1 model and uses it inside VoxCPM1's functions and its
noise filter; the storybook's voice loads VoxCPM2 with no noise filter (voice_book_worker.py) and reads
audio with librosa. PyPI's torchaudio is built against a different torch and would replace NVIDIA's.
Anything that does reach for it is told so here, instead of failing somewhere far away.
"""


def __getattr__(name):
    raise ImportError(f"torchaudio.{name} is not installed on the Spark (deploy/spark/voice-shim)")
