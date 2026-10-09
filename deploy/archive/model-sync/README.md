# 4090 model snapshot sync

This directory records the reproducible download entry point for the selected
official Wan snapshot staged on the shared 4090 server.

The active target is `Wan-AI/Wan2.2-TI2V-5B`. Previously downloaded model
directories are not removed by this script.

Each model is pinned to the revision recorded in `sync-models.sh`. The remote
download uses the standard Hugging Face HTTP transfer through `hf-mirror.com`
because the GPU server cannot currently reach `huggingface.co` directly, and
the mirror does not authorize Hugging Face's Xet CAS endpoint. The pinned commit
IDs remain the official Hugging Face revisions. The sync is safe to rerun to
resume an interrupted transfer.
