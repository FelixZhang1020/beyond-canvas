"""A line every ten seconds about the Spark's health, kept on its own disk.

Once the node froze and the only account of why was arithmetic: the
kernel's own messages need an admin group this account does not have. This
records what can be read without it — free memory, the graphics chip's
temperature, power and memory, disk, network, the running containers and which
programs hold the most memory, added up by name so forty-eight compilers show
as one line — and forces every line to disk before sleeping, so a freeze loses
at most the last ten seconds.

One file per day in ~/monitor, seven days kept. Stdlib only; start.sh runs it in tmux:

    python3 deploy/spark/spark_recorder.py
"""
import json
import os
import shutil
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path

FOLDER = Path.home() / 'monitor'
EVERY = 10
KEEP_DAYS = 7
GIB = 1024 ** 3


def meminfo():
    values = {}
    with open('/proc/meminfo') as handle:
        for line in handle:
            key, rest = line.split(':', 1)
            values[key] = int(rest.split()[0]) * 1024
    return values


def number(text):
    try:
        return float(text)
    except ValueError:
        return None


def gpu():
    """Temperature, power, use and memory; None wherever the GB10 does not report one."""
    fields = 'temperature.gpu,power.draw,utilization.gpu,memory.used'
    try:
        line = subprocess.run(['nvidia-smi', f'--query-gpu={fields}', '--format=csv,noheader,nounits'],
                              capture_output=True, text=True, timeout=5).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return {}
    return dict(zip(('temp_c', 'power_w', 'use_pct', 'memory_mib'), (number(v.strip()) for v in line.split(','))))


def default_interface():
    with open('/proc/net/route') as handle:
        for line in handle.readlines()[1:]:
            name, destination = line.split()[:2]
            if destination == '00000000':
                return name
    return None


def net_bytes(name):
    base = Path('/sys/class/net') / name / 'statistics'
    return int((base / 'rx_bytes').read_text()), int((base / 'tx_bytes').read_text())


def biggest(count=6):
    """Resident memory added up by program name, largest first."""
    totals = {}
    for status in Path('/proc').glob('[0-9]*/status'):
        try:
            lines = status.read_text().splitlines()
        except OSError:
            continue
        fields = dict(line.split(':', 1) for line in lines if ':' in line)
        rss = fields.get('VmRSS', '').split()
        if rss:
            name = fields.get('Name', '?').strip()
            size, processes = totals.get(name, (0, 0))
            totals[name] = (size + int(rss[0]) * 1024, processes + 1)
    top = sorted(totals.items(), key=lambda item: item[1][0], reverse=True)[:count]
    return [{'name': name, 'count': processes, 'gib': round(size / GIB, 2)} for name, (size, processes) in top]


def containers():
    try:
        return subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], capture_output=True, text=True,
                              timeout=5).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None


def sample(net, previous):
    """One reading. `previous` is (time, rx, tx) from the last one, for the network rate."""
    mem = meminfo()
    disk = shutil.disk_usage(Path.home())
    now, (rx, tx) = time.time(), net_bytes(net) if net else (0, 0)
    seconds = max(now - previous[0], 1e-6) if previous else None
    return {
        'at': round(now, 1),
        'mem_avail_gib': round(mem['MemAvailable'] / GIB, 2),
        'mem_total_gib': round(mem['MemTotal'] / GIB, 2),
        'swap_used_gib': round((mem.get('SwapTotal', 0) - mem.get('SwapFree', 0)) / GIB, 2),
        'load1': float(Path('/proc/loadavg').read_text().split()[0]),
        'disk_used_pct': round(100 * disk.used / disk.total, 1),
        'disk_free_gib': round(disk.free / GIB, 1),
        'net_down_kBps': round((rx - previous[1]) / seconds / 1024, 1) if seconds else None,
        'net_up_kBps': round((tx - previous[2]) / seconds / 1024, 1) if seconds else None,
        'gpu': gpu(),
        'top': biggest(),
        'containers': containers(),
    }, (now, rx, tx)


def write(row):
    """Append one line and force it onto the disk, so a freeze cannot keep it in memory."""
    FOLDER.mkdir(exist_ok=True)
    with (FOLDER / f'samples-{date.today():%Y-%m-%d}.jsonl').open('a') as handle:
        handle.write(json.dumps(row) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def prune():
    cutoff = f'samples-{date.today() - timedelta(days=KEEP_DAYS):%Y-%m-%d}.jsonl'
    for path in FOLDER.glob('samples-*.jsonl'):
        if path.name < cutoff:
            path.unlink()


def main():
    net, previous = default_interface(), None
    while True:
        row, previous = sample(net, previous)
        write(row)
        prune()
        time.sleep(EVERY)


if __name__ == '__main__':
    main()
