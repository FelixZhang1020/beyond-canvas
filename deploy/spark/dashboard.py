"""A plain-words view of the DGX Spark: what it is doing now, how full it is, and what it did lately.

Runs on the Spark, in the terminal you are logged into:   python3 ~/monitor/dashboard.py
That file and dashboard_jobs.py in ~/monitor are links to this copy, which sync.sh sends with the rest of
the project (they used to live only on the node); the class page's console draws its list of
work from the same dashboard_jobs.py, so the two screens agree. It only reads. Live figures come from the chip, /proc and Docker; history comes from the recorder's
files in ~/monitor and the job list the media services keep. Standard library only.
"""
import os, sys, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dashboard_jobs import (STUCK_MINUTES, duration, finished_jobs, finished_rows, finished_runs, now_rows, rough,
                            run, run_endings, samples, today_totals)
from memory_guard import CEILING_GIB, STOP_GIB   # the class's ceiling in use and the stop level under it

LOW_MEMORY_GB = STOP_GIB   # a running job is stopped under this; the node once froze when memory ran out
GREEN, YELLOW, RED, DIM, BOLD, OFF = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
# How each thing ended, in the colour and words this screen gives it: a class job by the outcome its
# service wrote, a test or a check by Docker's exit code (0 finished, 137/143 stopped from outside).
ENDED = {"done": (GREEN, "done in {}"), "cancelled": (YELLOW, "was cancelled after {}"),
         "refused": (YELLOW, "turned away, the service was busy"), "failed": (RED, "started but did not finish ({})"),
         "stopped": (YELLOW, "was stopped after about {}"), "error": (RED, "stopped with an error after about {}"),
         "unknown": ("", "ran for about {}")}


def chip():
    """Busy %, temperature and power, straight from the chip."""
    line = run("nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,power.draw",
               "--format=csv,noheader,nounits").strip().split(",")
    try:
        return float(line[0]), float(line[1]), float(line[2])
    except (ValueError, IndexError):
        return None, None, None


def memory():
    info = {}
    for row in Path("/proc/meminfo").read_text().splitlines():
        key, value = row.split(":", 1)
        info[key] = int(value.split()[0]) / 1024 / 1024
    return info["MemTotal"], info["MemAvailable"]


def bar(fraction, width=24):
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * width)
    colour = GREEN if fraction < 0.6 else YELLOW if fraction < 0.85 else RED
    return f"{colour}{'█' * filled}{DIM}{'░' * (width - filled)}{OFF}"


def spark_line(values, width=60):
    """One character per minute of the last hour; the tallest block is 100%."""
    if not values:
        return f"{DIM}(no history: the recorder is not running){OFF}"
    blocks, per = " ▁▂▃▄▅▆▇█", max(1, len(values) // width)
    groups = [values[i:i + per] for i in range(0, len(values), per)][-width:]
    return "".join(blocks[min(8, round(max(g) / 100 * 8))] for g in groups)


def chip_words(use, busy):
    if use is None:
        return f"{RED}cannot read the chip{OFF}"
    if use >= 60:
        return "working hard"
    if use >= 5:
        return "working"
    return "getting ready (loading a model into memory)" if busy else "resting, nothing to do"


def job_lines(row):
    """Two lines for one thing on the chip: who it is for and what it is, then how long, how far, how much."""
    group, running = row["group"], row["running_s"] or 0
    since_words = f"started {row['started_clock']}, " if row["started_clock"] else ""
    facts = [since_words + f"{'up' if group == 'service' else 'running'}"
             + ("" if row["running_s"] is None and group == "program" else f" {duration(running)}")]
    if row["usual_s"]:
        left = row["usual_s"] - running
        facts.append(f"usually {duration(row['usual_s'])}, {rough(left)} left" if left > 0
                     else f"{rough(-left)} longer than the usual {duration(row['usual_s'])}")
    elif group not in ("service", "program"):
        ago = row["reported_s_ago"]
        facts.append(f"last reported {rough(ago)} ago" if ago is not None else "has reported nothing yet")
    held = f" · holding {row['held_gb']:.0f} GB" if row["held_gb"] >= 0.5 else ""
    stuck = f"\n      {RED}looks stuck: the chip has done nothing for {STUCK_MINUTES} min{OFF}" if row["stuck"] else ""
    return [f"  • {group:<8} {row['what']}", f"      {' · '.join(facts)}{held}{stuck}"]


def history_lines(rows):
    width = max([22] + [len(row["what"]) for row in rows])
    lines = []
    for row in rows:
        colour, words = ENDED[row["outcome"]]
        # A class job's service timed it; a test's times come from the recorder, good to about 10 s.
        if row["outcome"] == "done" and row["group"] != "class":
            words = "done in about {}"
        lines.append(f"  {row['clock']}  {row['group']:<8} {row['what']:<{width}} "
                     f"{colour}{words.format(duration(row['seconds']))}{OFF}")
    return lines or [f"  {DIM}nothing recorded yet{OFF}"]


def today_lines(today):
    lines = [f"  {k['what']:<22} {k['done']} done, {k['refused']} turned away while busy, "
             f"{k['cancelled']} cancelled, {k['failed']} started but did not finish" for k in today["jobs"]]
    tests = today["tests"]
    if tests["finished"]:
        # Docker forgets how runs ended within minutes, so these two can only ever undercount: "including".
        known = [f"{tests[how]} {words}" for how, words in (("stopped", "stopped"), ("error", "with an error"))
                 if tests[how]]
        lines.append(f"  {'Tests and checks':<22} {tests['finished']} finished"
                     + (f", including {' and '.join(known)}" if known else ""))
    return lines


def frame():
    use, temp, power = chip()
    total, free = memory()
    recorded = samples(2 * 86400)
    hour = [s for s in recorded if s["at"] >= time.time() - 3600]
    finished = finished_jobs()
    rows = now_rows(hour, finished)
    busy = any(row["group"] != "service" for row in rows)
    latest = hour[-1] if hour else {}
    now = datetime.now()
    japan = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%H:%M")
    out = [f"{BOLD}DGX Spark, right now{OFF}   {now:%H:%M:%S} Spark time ({japan} in Japan)", ""]
    out.append(f"  Graphics chip  {bar((use or 0) / 100)} {use or 0:3.0f}%  {chip_words(use, busy)}")
    used = total - free
    warn = f"  {RED}running low{OFF}" if free < LOW_MEMORY_GB else (
        f"  {YELLOW}over the {CEILING_GIB:.0f} GB ceiling{OFF}" if used > CEILING_GIB else "")
    out.append(f"  Memory         {bar(used / total)} {used:3.0f} of {total:.0f} GB in use, {free:.0f} GB free{warn}")
    hottest = max((s.get("gpu", {}).get("temp_c") or 0 for s in hour), default=0)
    if temp is not None:
        out.append(f"  Temperature    {temp:.0f} °C   (highest in the last hour: {max(hottest, temp):.0f} °C)")
        out.append(f"  Power          {power:.0f} W")
    if latest:
        out.append(f"  Internet       downloading {latest.get('net_down_kBps', 0) / 1024:.1f} MB/s, "
                   f"uploading {latest.get('net_up_kBps', 0) / 1024:.1f} MB/s")
        out.append(f"  Disk           {latest.get('disk_used_pct', 0):.0f}% used, "
                   f"{latest.get('disk_free_gib', 0) / 1024:.1f} TB free")
    out += ["", f"{BOLD}Working on now{OFF}"]
    out += [line for row in rows for line in job_lines(row)] or [
        f"  {DIM}nothing: no picture, video or 3D job is running{OFF}"]
    ended = run_endings(finished_runs(recorded))
    today = today_lines(today_totals(finished, ended))
    out += ["", f"{BOLD}Finished lately{OFF} (newest first)"] + history_lines(finished_rows(finished, ended))
    if today:
        out += ["", f"{BOLD}Today so far{OFF}"] + today
    out += ["", f"{BOLD}Last hour{OFF}, one mark per minute"]
    out.append(f"  chip busy    {spark_line([s.get('gpu', {}).get('use_pct') or 0 for s in hour])}")
    out.append(f"  memory used  {spark_line([100 - 100 * s['mem_avail_gib'] / s['mem_total_gib'] for s in hour if s.get('mem_total_gib')])}")
    out += ["", f"{DIM}Updates every 3 seconds. Ctrl-C closes this screen; it only reads and changes nothing.{OFF}"]
    return "\n".join(out)


def edited_since(start, files=(Path(__file__), Path(__file__).with_name("dashboard_jobs.py"))):
    """True once either file of this screen was saved after it started, so it restarts itself on the new one."""
    try:
        return any(path.stat().st_mtime > start for path in files)
    except OSError:
        return False


if __name__ == "__main__":
    STARTED = time.time()
    if "--once" in sys.argv:
        print(frame())
        sys.exit(0)
    try:
        while True:
            text = frame()
            sys.stdout.write("\033[H\033[2J" + text + "\n")
            sys.stdout.flush()
            time.sleep(3)
            if edited_since(STARTED):   # a screen left open for days once kept showing a list edited hours before
                os.execv(sys.executable, [sys.executable, *sys.argv])
    except KeyboardInterrupt:
        print()
