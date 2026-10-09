"""The Spark monitor's view of jobs: what is running now and what ran and ended, whoever started it.

Imported by dashboard.py beside it. Every container is named for what it is, from TASKS — the tasks the
Spark has actually run, read from the recorder's history and the scripts that start them — and says
who it is for: a class, a test, a service kept running, or a check. A name nobody has listed yet is shown as unlisted, with its own name, so a new kind of task is
noticed rather than hidden.

It answers in data, not in text: the terminal screen (dashboard.py) and the class page's
console (studio/ops/spark_monitor.py) both read `picture()` and its parts, so the two can no longer disagree
about what is on the chip. They had: the console called a cancelled clip "last took 11m 17s", which was
the last one that finished, and counted memory in thousands where the screen counts in 1024s.
Standard library only; it only reads.
"""
import json, re, subprocess, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

KINDS = {"trellis": "3D model (TRELLIS.2)", "mesh": "3D model (Pixal3D)", "image": "Picture (FLUX)",
         "video": "Video clip (Wan)", "voice": "Voice"}
# What a running container makes, told by the model folder it mounts or the image it runs, and the
# kind the job list files it under once it finishes.
MAKES = [("/models/wan", "video"), ("/models/flux", "image"), ("pixal3d", "mesh"), ("trellis2", "trellis")]
MAKERS = {"image", "video", "trellis", "mesh"}   # jobs that make something; only these can look stuck
CLASS_JOB = re.compile(r"^beyond-canvas-media-[0-9a-f]{12}$")   # how media_server.py names every class job
# (container name, what it is, who it is for), first match wins. A service waits for work, so its chip
# sitting idle is normal, and it stopping is not work finishing.
TASKS = [
    (r"^beyond-canvas-flux-resident$", "Picture model (FLUX), kept loaded for the next picture", "service"),
    (r"^nemotron-engineer$", "Hall reviewer: NVIDIA Nemotron 3 Nano text model", "service"),
    (r"^nemotron-safety$", "Safety checker: NVIDIA Nemotron Content Safety", "service"),
    (r"^beyond-canvas-trellis-resident$", "3D model (TRELLIS.2), kept loaded for the next sketch", "service"),
    (r"^qwen-front$", "Class model: Qwen3.6 writes the chat lines and checks them, and writes the reviews", "service"),
    (r"^nemotron-vl$", "First voice trial: NVIDIA Nemotron Nano 12B VL reads the picture", "service"),
    (r"^bc-hearing", "Hearing on the chip: Whisper, the node's own transcription", "service"),
    # bin/blender names each run for its own process and the time. Who it is for is told by the folder it
    # runs in while it runs (the test copy or the class's own); once it has ended nothing records that.
    (r"^bc-blender-\d+-\d+$", "Blender: a 3D building tool or a render", "blender"),
    (r"^cosmos-clips$", "Video clip trial: NVIDIA Cosmos3 Edge on the hands-test drawings", "test"),
    (r"^asr-compare$", "Hearing trial: Whisper and NVIDIA Nemotron ASR on the same clips", "test"),
    (r"^magpie-say$", "Voice trial: NVIDIA Magpie speaks the eight test lines", "test"),
    (r"^voice-score$", "Voice trial: Whisper scores how clearly each voice is understood", "test"),
    (r"^nemotron-probe$", "Safety checker trial on test drawings (Nemotron)", "test"),
    (r"^gpu-probe", "Check that the chip works inside a container", "check"),
    (r"^geo-test-(\w+)-s(\d+)$", "3D model trial (TRELLIS.2): drawing {0}, variation {1}", "test"),
    (r"^beyond-canvas-media-hunt", "3D model freeze investigation (TRELLIS.2)", "test"),
    (r"^beyond-canvas-media-wanprobe$", "Video clip timing trial (Wan)", "test"),
    (r"^beyond-canvas-media-wansample$", "Video clip sample at the class setting (Wan)", "test"),
    (r"^beyond-canvas-media-wanhands$", "Video clip trial: keeping hands out (Wan)", "test"),
    (r"^beyond-canvas-media-wan", "Video clip trial (Wan)", "test"),
    (r"^beyond-canvas-media-(.+)$", "Trial: {0}", "test"),
]
# A name Docker made up because nobody gave one. The video tool starts dozens of these at a time, each for
# about a second, to cut and join frames; one lasting under a minute is a helper step, not work of its own.
MADE_UP_NAME = re.compile(r"^[a-z]+_[a-z]+\d?$")
STUCK_MINUTES = 10   # a normal step takes about 30 s; the chip idle this long while a job is open is not normal
HOME = Path.home()
SAMPLES = HOME / "monitor"
JOBS = HOME / "spark-media" / "media-extra" / "jobs.jsonl"


def run(*command, both=False):
    """A command's output, or nothing if it fails; `both` adds what it wrote to its error stream."""
    try:
        return subprocess.run(command, stdout=subprocess.PIPE, text=True, timeout=5,
                              stderr=subprocess.STDOUT if both else subprocess.DEVNULL).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def since(stamp):
    """Docker's UTC time stamp (nanoseconds and all) as seconds since the epoch, or None."""
    try:
        return datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def duration(seconds):
    seconds = round(seconds or 0)
    if seconds >= 3600:
        return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"
    return f"{seconds // 60} min {seconds % 60:02d} s" if seconds >= 60 else f"{seconds} s"


def clock(at):
    """The Spark's own time of day, for both screens: the class page is often opened an hour away (Japan)."""
    return f"{datetime.fromtimestamp(at):%H:%M}"


def rough(seconds):
    return "under a minute" if seconds < 60 else f"about {round(seconds / 60)} min"


def task(name, kind=None, image="", folder=""):
    """(what it is, who it is for) for a container, by its name, and for a class job by what it makes."""
    if CLASS_JOB.match(name):
        return KINDS.get(kind or "", "Picture, video or 3D model"), "class"
    for pattern, what, group in TASKS:
        found = re.match(pattern, name)
        if found:
            if group == "blender" and folder:
                group = "test" if "/beyond-canvas-test" in folder else "studio"
            return what.format(*found.groups()), group
    if MADE_UP_NAME.match(name):
        return ("Video tool step: cutting and joining frames" if "ffmpeg" in image else "Helper step"), "helper"
    return name, "unlisted"


def containers():
    """Every running container: name, when it started, its first process, image and what it makes."""
    ids = run("docker", "ps", "-q").split()
    fmt = ("{{.Name}}|{{.State.StartedAt}}|{{.State.Pid}}|{{.Config.Image}}|{{.Config.WorkingDir}}|"
           "{{range .Mounts}}{{.Destination}},{{end}}")
    boxes = []
    for row in run("docker", "inspect", "--format", fmt, *ids).splitlines() if ids else []:
        name, started, pid, image, folder, mounts = (row.split("|") + [""] * 6)[:6]
        kind = next((kind for key, kind in MAKES if key in mounts + image), None)
        boxes.append({"name": name.lstrip("/"), "started": since(started), "pid": int(pid or 0), "kind": kind,
                      "task": task(name.lstrip("/"), kind, image, folder), "held": 0.0})
    return boxes


def parent_chain(pid):
    """The process and every process above it, so a worker can be traced to the container it runs in."""
    chain = []
    while pid > 1 and len(chain) < 64:
        chain.append(pid)
        try:
            status = Path(f"/proc/{pid}/status").read_text()
        except OSError:
            break
        pid = int(next((row.split()[1] for row in status.splitlines() if row.startswith("PPid:")), 0))
    return chain


def chip_holders(boxes):
    """Hand each process's chip memory to its container; return what belongs to no container."""
    loose = []
    for row in run("nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits").splitlines():
        pid, _, mib = (part.strip() for part in row.partition(","))
        if not pid.isdigit():
            continue
        held = int(mib) / 1024 if mib.isdigit() else 0.0   # the chip may answer [N/A]
        owner = next((box for box in boxes if box["pid"] in parent_chain(int(pid))), None)
        if owner:
            owner["held"] += held
        else:
            loose.append((int(pid), held))
    return loose


def usual_seconds(kind, finished):
    """The middle of the last five times this kind of job finished well."""
    # Pictures under 15 s went to the picture model already loaded and never had a container of their
    # own, so they say nothing about a picture job that loads its model first.
    took = [job["seconds"] for job in finished if job.get("kind") == kind and job.get("outcome") == "ok"
            and (job.get("seconds") or 0) >= 15][-5:]
    return sorted(took)[len(took) // 2] if took else None


def chip_idle(hour):
    """True only when the recorder watched the whole last STUCK_MINUTES and the chip did nothing in it."""
    recent = [s.get("gpu", {}).get("use_pct") for s in hour if s.get("at", 0) >= time.time() - STUCK_MINUTES * 60]
    return len(recent) >= STUCK_MINUTES * 6 * 0.8 and all(use is not None and use < 5 for use in recent)


def box_row(box, finished, idle):
    """One running container: who it is for and what it is, since when, how far along, how much it holds."""
    (what, group), name = box["task"], box["name"]
    running = time.time() - box["started"] if box["started"] else None
    row = {"group": group, "what": what, "started": box["started"], "running_s": running,
           "started_clock": clock(box["started"]) if box["started"] else None,
           "usual_s": usual_seconds(box["kind"], finished) if group == "class" else None,
           "reported_s_ago": None, "held_gb": box["held"],
           "stuck": bool(idle and (running or 0) >= STUCK_MINUTES * 60 and box["kind"] in MAKERS
                         and group != "service")}
    if row["usual_s"] is None and group != "service":
        last = since(run("docker", "logs", "-t", "--tail", "1", name, both=True)[:30])
        row["reported_s_ago"] = time.time() - last if last else None
    return row


def loose_row(pid, held):
    """A program on the chip that no container owns, named by what it runs."""
    args = run("ps", "-o", "etimes=,args=", "-p", str(pid)).split()
    words = " ".join(Path(arg).name for arg in args[1:3]) or f"process {pid}"
    return {"group": "program", "what": f"{words}, outside the studio's containers", "started": None, "started_clock": None,
            "running_s": int(args[0]) if args and args[0].isdigit() else None, "usual_s": None,
            "reported_s_ago": None, "held_gb": held, "stuck": False}


def now_rows(hour, finished):
    """What the chip is doing now, one row per container and one per program outside them.

    How far along a job is cannot be read from outside it: its progress bar reaches Docker's log only
    when a line ends, which is when the whole bar is done. So a class job's time left is estimated from
    how long the same kind of job took lately, and a test says when it last reported anything.
    """
    boxes, idle = containers(), chip_idle(hour)
    loose = chip_holders(boxes)
    return [box_row(box, finished, idle) for box in boxes] + [loose_row(pid, held) for pid, held in loose]


def finished_runs(recorded):
    """Tests, checks and anything unlisted that ran and ended, as (name, first seen, last seen).

    Read from the container list the recorder writes every 10 s, so anything shorter is never seen. Class
    jobs are left out because the class services record their own; services, because one stopping is not
    work finishing; helper steps under a minute, because they are pieces of a job, not jobs.
    """
    running, runs = {}, []
    for sample in recorded:
        names = {n for n in sample.get("containers") or [] if not CLASS_JOB.match(n) and task(n)[1] != "service"}
        runs += [(name, *running.pop(name)) for name in list(running) if name not in names]
        running.update({name: (running.get(name, (sample["at"],))[0], sample["at"]) for name in names})
    return [(name, first, last) for name, first, last in runs if not (MADE_UP_NAME.match(name) and last - first < 60)]


def run_endings(runs):
    """(when it ended, who it was for, what it was, how it ended, how long it took) for each run.

    How it ended comes from Docker's exit code, which it keeps only for its last 256 events; an older run
    says only how long it ran. Without Docker's end time a run's times are good to about 10 s.
    """
    fmt = "{{.Time}} {{.Actor.Attributes.exitCode}} {{.Actor.Attributes.name}}"
    start = str(int(min((first for _, first, _ in runs), default=0)))
    events = [row.split(" ", 2) for row in run("docker", "events", "--since", start, "--until", "0s", "--filter",
              "type=container", "--filter", "event=die", "--format", fmt).splitlines()] if runs else []
    events = [(int(t), int(c), n) for t, c, n in (e for e in events if len(e) == 3) if t.isdigit() and c.isdigit()]
    ended = []
    for name, first, last in runs:
        when, code = next(((t, c) for t, c, n in events if n == name and first <= t <= last + 30), (None, None))
        how = "unknown" if code is None else "done" if code == 0 else "stopped" if code in (137, 143) else "error"
        end = when or last + 5
        what, group = task(name)
        ended.append((end, group, what, how, round((end - first + 5) / 10) * 10))
    return ended


def samples(seconds):
    """The recorder's lines for the last `seconds` (one line every 10 s)."""
    files = sorted(SAMPLES.glob("samples-*.jsonl"))[-2:]
    cutoff, out = time.time() - seconds, []
    for path in files:
        for row in path.read_text(errors="replace").splitlines():
            try:
                sample = json.loads(row)
            except ValueError:
                continue
            if sample.get("at", 0) >= cutoff:
                out.append(sample)
    return out


def finished_jobs():
    """Every line of the media services' job list that reads as a job, oldest first."""
    jobs = []
    for line in JOBS.read_text(errors="replace").splitlines() if JOBS.exists() else []:
        try:
            jobs.append(json.loads(line))
        except ValueError:
            continue
    return jobs


def outcome(job):
    """How a class job ended: done, cancelled, turned away at the door because the chip was taken, or failed."""
    if job.get("outcome") in ("ok", "cancelled"):
        return "done" if job["outcome"] == "ok" else "cancelled"
    return "refused" if (job.get("seconds") or 0) < 5 else "failed"


def finished_rows(finished, ended, count=8):
    """Everything that finished lately, class jobs and tests alike, newest first."""
    rows = [{"at": job.get("at", 0), "clock": clock(job.get("at", 0)), "group": "class", "what": KINDS.get(job.get("kind"), job.get("kind", "?")),
             "outcome": outcome(job), "seconds": job.get("seconds")} for job in finished]
    rows += [{"at": end, "clock": clock(end), "group": group, "what": what, "outcome": how, "seconds": took}
             for end, group, what, how, took in ended]
    return sorted(rows, key=lambda row: row["at"])[-count:][::-1]


def today_totals(finished, ended):
    """Today's class jobs by kind and how each ended, and how many tests and checks finished."""
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    kinds = {}
    for job in finished:
        if job.get("at", 0) >= midnight:
            name = KINDS.get(job.get("kind"), job.get("kind", "?"))
            kinds.setdefault(name, {"what": name, "done": 0, "refused": 0, "cancelled": 0, "failed": 0})
            kinds[name][outcome(job)] += 1
    # Docker forgets how runs ended within minutes, so stopped and error can only ever undercount.
    tests = Counter(how for end, _, _, how, _ in ended if end >= midnight)
    return {"jobs": list(kinds.values()),
            "tests": {"finished": sum(tests.values()), "stopped": tests["stopped"], "error": tests["error"]}}


def picture(count=8):
    """What is on the chip, what finished lately and today's totals: all either screen shows of the work."""
    recorded = samples(2 * 86400)
    hour = [s for s in recorded if s["at"] >= time.time() - 3600]
    finished = finished_jobs()
    ended = run_endings(finished_runs(recorded))
    return {"now": now_rows(hour, finished), "finished": finished_rows(finished, ended, count),
            "today": today_totals(finished, ended)}
