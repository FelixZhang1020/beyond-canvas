"""Start the showpiece exhibit: python -m studio.showpiece --port 7090 --model <path.blend>
[--profile stepfun] [--slot vlm.showpiece] [--runs .studio/showpiece/runs]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from studio.core.env import load_dotenv
from studio.server.ports import EXHIBIT_PORT
from studio.providers import build_client
from studio.showpiece import catalog
from studio.showpiece.driver import Driver
from studio.showpiece.serve import make_server
from studio.core.slots import load_profile, resolve


def main() -> None:
    parser = argparse.ArgumentParser(description="The showpiece exhibit: an agent drives the six skills on a model.")
    parser.add_argument("--port", type=int, default=EXHIBIT_PORT)
    parser.add_argument("--model", type=Path, default=None, help="the .blend the skills work on")
    parser.add_argument("--profile", default="stepfun")  # api until it was archived
    parser.add_argument("--slot", default="vlm.showpiece")   # StepFun, apart from the class chat
    parser.add_argument("--runs", type=Path, default=Path(".studio/showpiece/runs"))
    parser.add_argument("--cap", type=int, default=40)
    parser.add_argument("--quick", action="store_true", help="live runs render small and short, so the hall answers in minutes")
    args = parser.parse_args()
    load_dotenv()
    config = resolve(args.slot, load_profile(args.profile))
    config.options.setdefault("reasoning_effort", "low")
    client = build_client(config)
    driver = Driver(client, args.model, args.runs, cap=args.cap, agent_name=f"{config.model} via {config.provider}",
                    quick={**(catalog.QUICK if args.quick else {}), "slot": args.slot})   # the judge on the same slot
    httpd = make_server(args.port, driver)
    print(f"showpiece exhibit on http://127.0.0.1:{args.port}/  model {args.model or '(none)'}  agent {driver.agent_name}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
