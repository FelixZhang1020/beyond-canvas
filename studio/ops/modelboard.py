"""A board of lights: which model servers are up, measured when you look.

The published status page can only ever be a snapshot, because a page on the
web cannot reach a server on this machine. This is the other half: it runs
here, polls the ports itself, and tells you what is true now.

It reads the ports out of the profiles rather than carrying its own list, so
when the Spark arrives and eleven servers come up, the same page shows them
without an edit. That is also why it earns its place on day zero: it is the
fastest way to see whether the boot order in section 7 actually worked.

    uv run python -m studio.ops.modelboard                 # port 6001
    uv run python -m studio.ops.modelboard --profile spark # the eleven-slot machine

Nothing here reaches the network. Everything it needs — fonts, styles, script —
ships in the page, because the product's own rule is that pulling the cable
changes nothing, and a status page for an offline box must survive its own test.
"""

from __future__ import annotations

import argparse
import datetime
import errno
import json
import sys
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from studio.ops.modelusage import probe, usage_for
from studio.server.ports import BOARD_PORT, PAGE_PORT, off_convention
from studio.core.slots import PROFILE_DIR, load_profile
from studio.providers import LOCAL

# The board sits with the other things a person opens: 7060 is the studio page,
# 7010 is this. Both numbers, and the convention, come from studio/server/ports.py.

# Why the range starts at 7000. Browsers refuse a fixed list of ports outright:
# 6000 is X11's, so Chrome answers ERR_UNSAFE_PORT before opening a socket while
# curl fetches it happily, which once cost half an hour. `usable_port`
# still guards a port given on the command line, which has had no such check.
REQUESTED_PORT = 6000
BLOCKED_PORTS = frozenset({
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53, 69, 77, 79, 87,
    95, 101, 102, 103, 104, 109, 110, 111, 113, 115, 117, 119, 123, 135, 137, 138,
    139, 143, 161, 179, 389, 427, 465, 512, 513, 514, 515, 526, 530, 531, 532, 540,
    548, 554, 556, 563, 587, 601, 636, 989, 990, 993, 995, 1719, 1720, 1723, 2049,
    3659, 4045, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697, 10080,
})

PROBE_TIMEOUT = 0.6

# Ports this product really uses that are not model slots. A ports list that
# leaves them out is not a ports list: the transcription server is how the child
# is heard, and the page is the thing a teacher actually opens.
EXTRA_PORTS = (
    ("speech.in", "whisper-small-q5_1", "http://127.0.0.1:7290",
     "Hears the child and writes down what was said. On the 4090."),
    ("studio.page", "studio/serve.py", f"http://127.0.0.1:{PAGE_PORT}",
     "The teacher's page and the harness behind it."),
)


# Usage describes current callers, independently of endpoint reachability.
PURPOSES = {
    "vlm.studio": "课堂看图、反馈、对话与故事书文字。",
    "vlm.director": "反馈判卷；未配置独立安全组件时也负责作品安全筛查。",
    "safety.image": "作品进入课堂前的安全筛查。",
    "vlm.sketch": "素描入口的第一眼：看这张素描是不是只有方块、球和圆柱。是就直接拼出干净的立体形状，"
                  "其他（人头、水果、看不懂的）才交给 TRELLIS.2。每张素描都先经过它。",
    "vlm.figure": "彩画立体小雕塑的“写”：列出球、方块、胶囊等零件和颜色（32000 tokens，6 分钟上限）。",
    "vlm.figure.look": "彩画立体小雕塑的“看”：把做好的雕塑和原画并排比对，两次都通过才给孩子看；"
                       "与“写”分开配置。",
    "vlm.voice_lab": "独立成人语音实验的对话；与几何定位共享 Step3 服务。",
    "video.animation": "彩画短视频预览：4090 本地部署目标为 Wan 2.2 TI2V-5B，也可用于故事书视频页。",
    "mesh.portrait": "素描三维重建；多模型方案的 TRELLIS.2 使用 4090，老师可手动选择云端 Pixal3D，不自动付费重试。",
    "mesh.fast": "保留的 InstantMesh 配置；当前课堂素描入口不调用。",
    "mesh.premium": "Spark 规划插槽；当前课堂未接入。",
    "safety.reader": "NVIDIA Nemotron 3.5 Content Safety：studio-safety 里的第二道安全检查，入口只拦色情内容，出口任何标记都拒绝；课堂接入（StepFun First），常驻 Spark，视频生成时让出内存。",
    "llm.engineer": "大殿重建的工程师式复核：NVIDIA Nemotron 只读数字、不看图，只给意见；课堂不调用。",
    "depth": "Spark 深度模型规划；当前课堂未接入。",
    "tts.studio": "语音配置插槽；课堂朗读由启动时注入的 voice 服务决定。",
    "tts.export": "故事朗读配置插槽；当前故事书复用课堂 voice 服务。",
    "speech.in": "Whisper 本机转写；老师确认文字后进入对话。",
    "studio.page": "课堂、课程作品集与三维评测展示入口。",
}
CONFIG_ONLY = {"mesh.fast", "mesh.premium", "depth", "tts.studio", "tts.export"}


def usable_port(wanted: int) -> int:
    """The nearest port at or above `wanted` that a browser will actually open."""
    port = wanted
    while port in BLOCKED_PORTS:
        port += 1
    return port


def port_of(base_url: str) -> int | None:
    """The port in a base URL, or None when there is not one to read."""
    tail = (base_url or "").rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else None


@dataclass
class Light:
    """One row on the board: a thing that should be listening, and whether it is."""

    slot: str
    model: str
    url: str
    purpose: str = ""
    usage: str = "配置路径"
    size_gb: float | None = None
    hosted: bool = False
    # None means the question does not apply here, which is not the same as down.
    up: bool | None = None
    serving: str = ""
    latency_ms: int | None = None
    note: str = ""
    clash: list[str] = field(default_factory=list)
    # Measured from the process holding the port, never from the profile: the
    # question is what is loaded, and a config file only says what was intended.
    paths: list[str] = field(default_factory=list)
    disk_gb: float | None = None
    ram_gb: float | None = None

    @property
    def where(self) -> str:
        """Local or online. On a children's product this is the privacy answer."""
        return "online" if self.hosted else "local"

    @property
    def port(self) -> int | None:
        return port_of(self.url)

    def as_dict(self) -> dict:
        return {
            "slot": self.slot, "model": self.model, "url": self.url,
            "purpose": self.purpose, "usage": self.usage, "size_gb": self.size_gb, "hosted": self.hosted,
            "up": self.up, "serving": self.serving, "latency_ms": self.latency_ms,
            "note": self.note, "clash": self.clash, "port": self.port,
            "where": self.where, "paths": self.paths,
            "disk_gb": self.disk_gb, "ram_gb": self.ram_gb,
        }


def read_board(profile_name: str, probe=probe) -> list[Light]:
    """Measure every port this profile expects, plus the ones outside it.

    Raises rather than returning an empty board for a profile that does not
    exist: a board with no lights on it looks like a dead machine, and that
    would be a lie about a typo.
    """
    path = PROFILE_DIR / f"{profile_name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"no profile named {profile_name!r} in {PROFILE_DIR}")

    lights: list[Light] = []
    for slot, config in sorted(load_profile(profile_name).items()):
        options = config.options or {}
        url = options.get("base_url", "")
        lights.append(Light(
            slot=slot,
            model=config.model,
            purpose=PURPOSES.get(slot, "用途尚未核对。"),
            usage="仅保留配置" if slot in CONFIG_ONLY else "独立实验" if slot == "vlm.voice_lab" else "配置路径",
            url=url,
            size_gb=options.get("size_gb"),
            hosted=config.provider not in LOCAL,
            note="云端 API：未发送推理请求，在线可用性未验证。" if not url else "",
        ))
    # An extra port fills a gap; it never overrides a profile. `speech.in` was
    # listed below because no profile carried it, and later the spark
    # profile gained it — which lit the board twice for one model until this
    # guard. The profile is the canonical answer wherever it has one.
    named = {light.slot for light in lights}
    for slot, model, url, purpose in EXTRA_PORTS:
        if slot in named:
            continue
        lights.append(Light(slot=slot, model=model, url=url, purpose=PURPOSES.get(slot, purpose)))

    _light_them(lights, probe)
    _mark_clashes(lights)
    return lights


def _light_them(lights: list[Light], probe) -> None:
    """Ask each local port, and leave the hosted ones alone.

    Polling localhost for a hosted model would report it down forever, which
    reads as a fault rather than as a model living somewhere else.
    """
    for light in lights:
        if light.hosted or not light.url:
            continue
        started = time.monotonic()
        answer = probe(light.url, timeout=PROBE_TIMEOUT)
        light.latency_ms = int((time.monotonic() - started) * 1000)
        light.up = answer is not None
        light.serving = answer or ""
        if not light.up:
            light.note = "本轮健康探测未成功；可能未启动、超时或接口不匹配。"
            continue
        _measure(light)


def _measure(light: Light) -> None:
    """Ask the process holding the port what it loaded and what that costs.

    Only for a slot that answered: one that is down occupies no memory at all,
    and a zero would be a measurement where there is none.
    """
    light.paths, light.disk_gb, light.ram_gb = usage_for(light.port or 0)


def _mark_clashes(lights: list[Light]) -> None:
    """Two things cannot hold one port, and a config file will not say so.

    `studio/serve.py` defaulted to 8080 and so did the local studio model, so
    whichever started second could not bind and the board reported the page as
    up when what answered was the model. Found by listing what was
    actually listening, and fixed by the port convention straight away. This
    check stays: the convention is enforced in tests, and this is what tells
    someone at a glance when two servers on one machine have collided anyway.
    """
    seen: dict[int, list[Light]] = {}
    for light in lights:
        if light.port:
            seen.setdefault(light.port, []).append(light)
    for sharing in seen.values():
        if len(sharing) < 2:
            continue
        for light in sharing:
            # Request aliases (for example vlm.sketch with a geometry prefill)
            # use the same resident model. They do not start a second server.
            light.clash = [other.slot for other in sharing if other is not light
                           and not (light.model and light.model == other.model
                                    and light.url.rstrip('/') == other.url.rstrip('/'))]


# --- The page ----------------------------------------------------------------

# The page lives beside this file rather than inside it, the way the skills keep
# their prompts: it is content, and a 200-line string in the middle of a module
# hides the twenty lines of logic that matter. System faces only, and no network
# call of any kind, because this is the one page whose job is to prove that this
# machine needs none.
PAGE_FILE = Path(__file__).parents[1] / "assets" / "modelboard.html"

REFRESH_SECONDS = 5


def page_html(profile_name: str, port: int, seconds: int = REFRESH_SECONDS) -> str:
    """The page, with the numbers a reader needs baked in rather than guessed."""
    return PAGE_FILE.read_text(encoding="utf-8").format(
        profile=profile_name, port=port, requested=REQUESTED_PORT, seconds=seconds
    )


def serve(profile_name: str, port: int) -> None:
    """Hold the board open until interrupted."""

    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, kind: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - the name http.server requires
            from studio.server.console_panel import serve_console
            if serve_console(self):
                return
            if self.path.startswith("/api/lights"):
                lights = read_board(profile_name)
                payload = {
                    "profile": profile_name,
                    "at": datetime.datetime.now().strftime("%H:%M:%S"),
                    "lights": [light.as_dict() for light in lights],
                }
                self._send(json.dumps(payload).encode(), "application/json")
                return
            self._send(page_html(profile_name, port).encode(), "text/html; charset=utf-8")

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - base signature
            """Silence. A page polling every few seconds would fill the terminal."""

    class Board(ThreadingHTTPServer):
        """A thread per reader.

        One reading runs lsof and ps for every model that answered, so it takes
        seconds; the page asks for one every five. Served one at a time, the
        queue never drained and the board stopped answering anything, the static
        page included. A reading is independent of every other, so the fix is to
        let them overlap.
        """

        daemon_threads = True

    try:
        server = Board(("127.0.0.1", port), Handler)
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        _explain_busy_port(port)
        return

    with server:
        print(f"Model board on http://127.0.0.1:{port}/  (profile: {profile_name})")
        print("Ctrl-C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nBoard closed.")


def _explain_busy_port(port: int) -> None:
    """Say what is on the port and what to do, rather than raising errno 48.

    Reported as "command crashed": starting the board while a
    board was already running printed twenty lines of traceback. Two things
    were wrong with that. It reads as a defect when it is the ordinary case of
    having started one already, and the remedy — open the one that is running,
    or pass another port — was nowhere in the output.
    """
    if probe(f"http://127.0.0.1:{port}") is not None:
        print(f"A board is already running on {port}. Open http://127.0.0.1:{port}/")
    else:
        print(f"Port {port} is taken by something that is not a board.")
    print(f"To run a second one somewhere else: --port {usable_port(port + 10)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Which model servers are actually up")
    parser.add_argument("--profile", default="local", help="local, cloud or spark")
    parser.add_argument("--port", type=int, default=BOARD_PORT)
    parser.add_argument("--once", action="store_true", help="print the board and exit")
    arguments = parser.parse_args()

    if arguments.once:
        for light in read_board(arguments.profile):
            state = "hosted" if light.hosted else ("up" if light.up else "down")
            print(f"{state:7} {light.slot:14} {light.model:26} {light.url or '-'}")
        return
    stray = off_convention(arguments.port)
    if stray:
        print(stray, file=sys.stderr)
    serve(arguments.profile, usable_port(arguments.port))


if __name__ == "__main__":
    main()
