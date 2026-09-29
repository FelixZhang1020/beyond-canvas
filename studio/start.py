"""Start the classroom on StepFun First, the studio's only deployment.

StepFun's models on the subscription read, judge, speak and hear; pictures, 3D and the
clip run on the hosted DGX Spark (the Mac + 4090 way was archived, and a
class opens at the Spark's own address; deploy/spark/start.sh). On the Mac this is for
checks and development. No downloads or installation; keep this command running for the page.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

import httpx

from studio.core.env import load_dotenv
from studio.server.ports import PAGE_PORT

ROOT = Path(__file__).resolve().parents[1]


# What a run picks when nobody names one. Written once here so the deploy guide can
# name it. There is no fallback since API First, which needed no hardware and was
# what a machine without a GPU box used to start, was archived: such a
# machine now refuses, naming what is missing.
DEFAULT_DEPLOYMENT = 'stepfun'


def ready(url):
    try:
        with httpx.Client(trust_env=False, timeout=2) as client:
            response = client.get(url)
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def choose(asked, state):
    """The deployment to start: the one asked for, else the saved one, else the default."""
    import json
    from studio.core.deployments import ARCHIVED, DEPLOYMENTS, unknown
    if asked in ARCHIVED:
        raise RuntimeError(str(unknown(asked)))
    selected = asked
    if selected is None and state.exists():
        saved = json.loads(state.read_text()).get('deployment')
        if saved == 'current':
            raise RuntimeError('Legacy current selection is ambiguous; explicitly choose --deployment stepfun.')
        if saved in ARCHIVED:
            print(f'{ARCHIVED[saved]} was archived; starting StepFun First.', flush=True)
            saved = DEFAULT_DEPLOYMENT
        selected = saved
    selected = selected or DEFAULT_DEPLOYMENT
    if selected not in DEPLOYMENTS:
        raise RuntimeError('Unknown saved deployment')
    return selected


def main(argv=None):
    from studio.core.deployments import ARCHIVED, DEPLOYMENTS, missing_keys
    from studio.core.deployment_checks import check_profile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=PAGE_PORT)
    # Archived names are accepted here only so the refusal can say they were archived.
    parser.add_argument('--deployment', choices=(*DEPLOYMENTS, *ARCHIVED), default=None)
    parser.add_argument('--check', action='store_true', help='read-only component checks')
    args = parser.parse_args(argv)
    os.chdir(ROOT)
    load_dotenv()
    selected = choose(args.deployment, ROOT / '.studio/deployment.json')
    report = check_profile(selected)
    for item in report['components']:
        print(f"{item['slot']}: {item['status']}", flush=True)
    # A fresh copy has no keys of ours: name the missing one and where it goes, not only the slots it leaves down.
    missing = missing_keys(selected)
    if missing:
        print(f"no {' or '.join(missing)} on this machine: copy .env.example to .env beside README.md and put your "
              "own key in (README, \"Your API keys\")", flush=True)
    if args.check:
        return 0 if report['ready'] else 1
    # Hearing deserves its own message, because it is the one slot a teacher
    # notices only when a child speaks.
    hearing = next((c for c in report['components'] if c['slot'] == 'speech.in'), None)
    if hearing is not None and hearing['status'] != 'ready':
        raise RuntimeError(
            f"Nothing is hearing for {selected}: StepFun's transcription (stepaudio-2.5-asr) needs "
            'STEPFUN_API_KEY and a reachable api.stepfun.com.')
    if not report['ready']:
        raise RuntimeError('Required component checks failed; no model fallback was started.')
    if ready(f'http://127.0.0.1:{args.port}/api/health'):
        raise RuntimeError(f'A classroom is already on port {args.port}.')
    subprocess.run(['sh', 'studio/page/build.sh'], check=True)
    os.execv(sys.executable, [sys.executable, '-m', 'studio.serve', '--profile', selected,
                             '--port', str(args.port), '--deployment', selected])
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
