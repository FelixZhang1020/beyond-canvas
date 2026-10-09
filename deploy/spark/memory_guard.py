"""Run one command, and stop it before it can freeze the Spark; and the memory rule every class job keeps.

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

Two rules live here, one for each kind of work, and they are not the same number:

- A build keeps FLOOR_GIB available (above). A compile has no measured peak, so it is given a wide margin.
- A class job (media_spark.py) and a kept-loaded model's load (the *-load.sh scripts) keep the node at or
  under CEILING_GIB in use, where "in use" is total minus available, the figure the node's monitor shows
  (operator). What a new load may still take is room_gib(). A job or load already running is stopped the
  moment available memory falls under STOP_GIB (low()): the lowest level the node has been measured to
  survive, with swap taking the rest (docs/measured/memory-ceiling-on-the-spark.md).

    python3 memory_guard.py --room    # whole GiB a class load may still take under the ceiling; negative when over
    python3 memory_guard.py --low     # exit 0 when a running job or load must stop, 1 otherwise

MEMORY_GUARD_MEMINFO names another file to read instead of /proc/meminfo,
which is how the guard is proved to cancel a real build without starving the node.
"""
import argparse
import math
import os
import signal
import subprocess
import sys
import time

MEMINFO = os.environ.get('MEMORY_GUARD_MEMINFO', '/proc/meminfo')
# GiB of available memory a build never gives away.
FLOOR_GIB = 24.0
# GiB in use (total minus available) that a class job or a kept-loaded model's load may not take the node past.
CEILING_GIB = 115.0
# GiB available under which a running class job or load is stopped. Measured: the node ran at 6 GiB available
# with 11.6 GiB in swap and did not freeze; nothing below has been measured.
STOP_GIB = 6.0


def _meminfo():
    """MemTotal and MemAvailable in GiB, as the kernel reports them."""
    found = {}
    with open(MEMINFO) as meminfo:
        for line in meminfo:
            key, _, rest = line.partition(':')
            if key in ('MemTotal', 'MemAvailable'):
                found[key] = int(rest.split()[0]) / 1024 / 1024
    if 'MemAvailable' not in found:
        raise RuntimeError(f'no MemAvailable line in {MEMINFO}')
    return found.get('MemTotal', 0.0), found['MemAvailable']


def available_gib():
    return _meminfo()[1]


def total_gib():
    return _meminfo()[0]


def used_gib():
    """Memory in use as the node's monitor counts it: total minus available."""
    return total_gib() - available_gib()


def room_gib():
    """GiB a class load may still take before the node passes the ceiling; negative once it has."""
    return CEILING_GIB - used_gib()


def low():
    """Whether a running class job or load must stop now: available memory under the stop level."""
    return available_gib() < STOP_GIB


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
    parser.add_argument('--room', action='store_true', help='print the whole GiB a class load may still take')
    parser.add_argument('--low', action='store_true', help='exit 0 when a running class job must stop')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.room:
        print(math.floor(room_gib()))
        return 0
    if args.low:
        return 0 if low() else 1
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
