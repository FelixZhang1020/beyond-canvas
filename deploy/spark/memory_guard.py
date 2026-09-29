"""Run one command, and stop it before it can freeze the Spark.

A DGX Spark that runs out of memory does not kill the largest process; it
freezes. Once a flash-attn compile took the node down for fifty
minutes and only the organisers could bring it back. This reads the kernel's
available-memory figure every second and, if it falls under the floor,
interrupts the command as Ctrl-C would, then kills it. Interrupting
`docker build` makes Docker cancel the build, compilers included.

Every thirty seconds it logs the lowest figure it saw, so the next build can
be sized from a measurement rather than a guess. Stdlib only, for the node's
system python3:

    python3 memory_guard.py --floor 24 -- docker build ...

MEMORY_GUARD_MEMINFO names another file to read instead of /proc/meminfo,
which is how the guard is proved to cancel a real build without starving the node.
"""
import argparse
import os
import signal
import subprocess
import sys
import time

MEMINFO = os.environ.get('MEMORY_GUARD_MEMINFO', '/proc/meminfo')
# GiB of available memory never given away: by a build here, by a class's job in media_spark.py.
FLOOR_GIB = 24.0


def available_gib():
    with open(MEMINFO) as meminfo:
        for line in meminfo:
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) / 1024 / 1024
    raise RuntimeError(f'no MemAvailable line in {MEMINFO}')


def stop(child):
    """Interrupt the command's whole process group, then kill whatever is left."""
    for sig, grace in ((signal.SIGINT, 20), (signal.SIGKILL, 10)):
        try:
            os.killpg(child.pid, sig)
            child.wait(timeout=grace)
            return
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            continue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--floor', type=float, default=FLOOR_GIB, help='GiB of available memory to keep free')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    child = subprocess.Popen(command, start_new_session=True)
    lowest, since = available_gib(), time.monotonic()
    while child.poll() is None:
        free = available_gib()
        lowest = min(lowest, free)
        if free < args.floor:
            print(f'memory_guard: {free:.1f} GiB available, under the {args.floor:g} GiB floor; '
                  f'stopping {command[0]}', flush=True)
            stop(child)
            return 3
        if time.monotonic() - since >= 30:
            print(f'memory_guard: lowest available {lowest:.1f} GiB', flush=True)
            lowest, since = free, time.monotonic()
        time.sleep(1)
    return child.returncode


if __name__ == '__main__':
    sys.exit(main())
