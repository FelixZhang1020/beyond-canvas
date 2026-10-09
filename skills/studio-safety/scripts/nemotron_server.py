"""Hold NVIDIA's safety model in memory and answer about one picture at a time.

The second reader of the safety skill is Nemotron 3.5 Content Safety, 4B, about 11 GB once loaded.
Loading takes twelve seconds and a look 0.4 (measured on the DGX Spark), so it is loaded
once and asked over a small local route:

    POST /look    {"image": "data:image/png;base64,...", "question": "..."}  ->  {"answer": "..."}
    GET  /health  ->  {"ready": true}

It listens on 127.0.0.1 only. From another machine it is reached through an SSH tunnel, never a
public port, so it needs no password of its own. One look at a time: the model is not asked two
things at once. The answer is returned as the model wrote it and is never logged, because the
model's words about a child's drawing go no further than the skill's reader (nemotron.py).

It runs NVIDIA's stock rules (operator); the studio's own policy is the measured
fallback and is asked for with `--studio-policy`. The weights are read whole, never memory-mapped:
on the GB10 a memory-mapped load measured about fifty times slower.

Runs where torch and transformers live, which on the Spark is the diffusers container:
    python skills/studio-safety/scripts/nemotron_server.py MODEL_DIR [--port 7140] [--studio-policy]
"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 7140
LARGEST_REQUEST = 24 * 1024 * 1024
MAX_NEW_TOKENS = {"stock": 100, "studio": 800}      # with a policy of our own the model thinks first


def load(model_dir: Path):
    import torch
    from safetensors.torch import load as read_tensors
    from transformers import AutoProcessor, Gemma3ForConditionalGeneration

    state = {}
    for shard in sorted(model_dir.glob("*.safetensors")):
        state.update(read_tensors(shard.read_bytes()))
    config = Gemma3ForConditionalGeneration.config_class.from_pretrained(model_dir, local_files_only=True)
    model = Gemma3ForConditionalGeneration.from_pretrained(None, config=config, state_dict=state, torch_dtype=torch.bfloat16)
    return model.to("cuda").eval(), AutoProcessor.from_pretrained(model_dir, local_files_only=True)


def ask(model, processor, picture, question: str, policy: str | None) -> str:
    """One look. `picture` is a PIL image; `policy` is our own rules, or None for NVIDIA's."""
    import torch

    messages = [{"role": "user", "content": [{"type": "image", "image": picture.convert("RGB")},
                                             {"type": "text", "text": question}]}]
    extra = {"enable_thinking": True, "custom_policy": policy} if policy else {"enable_thinking": False}
    inputs = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True,
                                           return_tensors="pt", request_categories="/categories", **extra).to(model.device)
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS["studio" if policy else "stock"], do_sample=False)
    return processor.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)


def picture_bytes(data_uri: object) -> bytes:
    """The picture inside a data URI. Raises ValueError for anything else."""
    if not isinstance(data_uri, str) or not data_uri.startswith("data:image/") or ";base64," not in data_uri:
        raise ValueError("the image must be a data:image/...;base64, URI")
    try:
        return base64.b64decode(data_uri.split(";base64,", 1)[1], validate=True)
    except binascii.Error as error:
        raise ValueError("the image is not valid base64") from error


def serve(answer, port: int = PORT) -> ThreadingHTTPServer:
    """The route, around any `answer(picture_bytes, question) -> str`; the caller runs serve_forever."""
    one_at_a_time = threading.Lock()

    class Look(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:      # nothing about a picture is written anywhere
            return

        def _send(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            self._send(200, {"ready": True}) if self.path == "/health" else self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if self.path != "/look" or not 0 < length <= LARGEST_REQUEST:
                return self._send(404 if self.path != "/look" else 400, {"error": "POST /look with a picture and a question"})
            try:
                body = json.loads(self.rfile.read(length))
                picture, question = picture_bytes(body.get("image")), body.get("question")
                if not isinstance(question, str) or not question.strip():
                    raise ValueError("a question is needed beside the picture")
            except (ValueError, AttributeError) as error:
                return self._send(400, {"error": str(error)})
            try:
                with one_at_a_time:
                    said = answer(picture, question)
            except Exception as error:      # a failed look is the client's "unavailable", never a dead server
                return self._send(500, {"error": type(error).__name__})
            self._send(200, {"answer": said})

    return ThreadingHTTPServer(("127.0.0.1", port), Look)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve NVIDIA's safety model to the safety skill")
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--studio-policy", action="store_true", help="the studio's own policy instead of NVIDIA's stock rules")
    args = parser.parse_args(argv)
    from PIL import Image

    policy = None
    if args.studio_policy:
        import importlib.util
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))      # nemotron.py reads studio.core.errors
        spec = importlib.util.spec_from_file_location("studio_policy_rule", Path(__file__).with_name("nemotron.py"))
        rule = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = rule
        spec.loader.exec_module(rule)
        policy = rule.inference_policy()
    model, processor = load(args.model_dir)
    server = serve(lambda picture, question: ask(model, processor, Image.open(io.BytesIO(picture)), question, policy), args.port)
    print(f"SAFETY READER ready on 127.0.0.1:{args.port}, {'the studio policy' if policy else 'stock rules'}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
