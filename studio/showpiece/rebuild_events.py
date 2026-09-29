"""Add every logged event of the adopted hall build to the presentation record.

The log stays in the private run folder. The checked-in record carries short,
path-free excerpts and the exact event order, not Blender's verbose output, and the
harness facts rebuild_facts.py reads from the run folder and the code.
Usage: python studio/showpiece/rebuild_events.py [path/to/the/run/events.jsonl]
(the run folder is private to the Mac that ran it, so a worktree names it).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "skills/load-path/scripts")]
from quake import SITE, ground_path, sideways_pull  # noqa: E402
from studio.showpiece.rebuild_facts import call_fields, harness_facts, judged, mark_repairs  # noqa: E402

RUN_NAME = "20260921-134852-5fb51a"
RUN = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / f".studio/showpiece/rebuilds/{RUN_NAME}/events.jsonl"
RECORD = ROOT / "studio/showpiece/page/rebuild-record.json"

TOOLS_ZH = {
    "survey": "测量原殿", "read": "读取资料", "platform": "放置台基", "columns": "立柱",
    "ties": "安系梁", "walls": "砌墙", "brackets": "搭斗拱", "frames": "调整屋架",
    "purlins": "铺檩条", "rafters": "铺椽", "roof": "盖屋面", "inventory": "清点构件",
    "bearing": "检查承托", "weights": "核算承重", "settle": "松手测重力",
    "shake": "地震与侧拉", "likeness": "检查相似度", "judge": "看图复核",
    "review": "请求工程意见", "faults": "读取故障报告",
}
# How an earlier run ended, for the steps rebuild_runs.py writes from its log.
ENDINGS = {
    "stop": ("运行停止 · 未交付", "模型把整个思考预算用完却没有回答，运行就此停止；Harness 没有交付任何东西。"),
    "final": ("声明完成 · 交给采纳门", "模型说大殿已完成，由采纳门决定能否交付。"),
}
DETAILS = {
    "inventory": "清点当前大殿的构件和类别。",
    "bearing": "逐件检查承托关系、悬空件和力的传递。",
    "weights": "计算总重、雪载和立柱承压。",
    "settle": "松开当前大殿的可动构件，在重力下检查 3 秒。",
    "shake": "地面以 0.20 g、2.5 Hz 晃动，再施加 0.07 g 侧拉。",
    "likeness": "比较正面、侧面和俯视轮廓，并寻找穿出屋顶的构件。",
    "judge": "查看原殿与重建殿的对照图，判断外观。",
    "review": "请求工程建议；原次本地服务未响应，此项不影响验收。",
    "faults": "Harness 把检查找到的问题按构件归类，交回模型。",
}
def think_title(tool: str | None) -> str:
    return f"思考 · 准备{TOOLS_ZH.get(tool, '下一步')}"


def act_words(tool: str | None, args: dict) -> tuple[str, str]:
    detail = f"读取 {args.get('file', '资料')}，为下一步取数。" if tool == "read" else DETAILS.get(tool, "按测量参数放置或更新构件。")
    return TOOLS_ZH.get(tool, tool or "执行工具"), detail


RESULT = re.compile(r"^(?:SURVEY|ANATOMY|BEARING|LOADS|SETTLE|SHAKE|LIKENESS|BRIEF|PLACED|REVIEW|REFUSED|FAULTS|.*error:).*$")


def excerpt(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if RESULT.match(line):
            return line[:360]
    return ""


def main() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    raw = RUN.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record["source_events_sha256"]:
        raise SystemExit("the historical event log no longer matches the presentation record")
    events = [json.loads(line) for line in raw.splitlines() if line]
    if [event["step"] for event in events] != list(range(1, 146)):
        raise SystemExit("the historical event sequence is incomplete")
    curated = {chapter["step"]: chapter for chapter in record["chapters"]}
    placement = {action["step"]: action for action in record["placements"]}
    start = datetime.fromisoformat(events[0]["at"])
    frame, layer_count, focus = "temple", 0, None
    cutaways = set(record["cutaway_frames"])
    steps = []
    for i, event in enumerate(events):
        number, original_kind = event["step"], event["kind"]
        tool = event.get("tool")
        if number in placement:
            frame = f"step-{number}"
        if number in curated and curated[number].get("layers_visible"):
            layer_count = curated[number]["layers_visible"]
        if number in curated and curated[number].get("focus"):
            focus = curated[number]["focus"]
        if number >= 145:
            focus = None
        known = curated.get(number)
        if original_kind == "think":
            next_tool = events[i + 1].get("tool") if i + 1 < len(events) else None
            title = f"思考 · 准备{TOOLS_ZH.get(next_tool, '下一步')}"
            detail = event.get("text", "").split("\n", 1)[0][:230]
        elif original_kind == "look":
            title, detail = "看图复核", "Agent 查看两座大殿的对照图，再决定是否交付。"
        elif original_kind == "final":
            title, detail = "完成交付", "全部规定检查通过，交付重建的大殿。"
        else:
            title = TOOLS_ZH.get(tool, tool or "执行工具")
            detail = DETAILS.get(tool, "按测量参数放置或更新构件。")
            if tool == "read":
                detail = f"读取 {event.get('args', {}).get('file', '资料')}，为下一步取数。"
            if number in (48, 50):
                detail = "end-beams=3,3 被当时的整数参数校验拒绝，模型没有改动。"
        if known:
            title, detail = known["title"], known["detail"]
        step = {
            "step": number,
            "elapsed": round((datetime.fromisoformat(event["at"]) - start).total_seconds()),
            "kind": original_kind,
            "tool": tool,
            "title": title,
            "detail": detail,
            "frame": frame,
            "layers_visible": layer_count if 6 <= number <= 32 else 0,
            "cutaway": frame in cutaways and 52 <= number < 138,
            "focus": focus if 44 <= number < 145 else None,
            "duration_ms": 1050 if original_kind == "think" else 1500,
            **call_fields(event, RUN_NAME),
        }
        if original_kind == "think":
            step["evidence"] = event.get("text", "")[:800]
        elif original_kind in ("look", "final"):
            step["evidence"] = event.get("text", "")[:800]
        else:
            step["evidence"] = judged(event) if tool == "judge" else excerpt(event.get("text", ""))
            step["args"] = {key: value for key, value in event.get("args", {}).items()
                            if key not in ("out_dir", "out") and not any(s in key.lower() for s in ("key", "token", "secret", "password"))}
        if tool in ("settle", "shake"):
            step["physics"] = tool
            step["duration_ms"] = 3200 if tool == "settle" else 6200
        elif tool == "weights" and number in (38, 132):
            step["duration_ms"] = 5200
        elif tool == "brackets" and number == 18:
            step["duration_ms"] = 15000
            step["chapter"] = "brackets"          # the one call the bracket close-up takes apart
        elif tool == "likeness":
            step["duration_ms"] = 2400
        elif number in (52, 54, 68, 82, 96, 110, 126, 138):
            step["duration_ms"] = 2400
        steps.append(step)
    record["steps"] = mark_repairs(steps)
    record["harness"] = harness_facts(RUN.parent, events)
    frames, fps = 144, 24
    record["physics_protocol"] = {
        "fps": fps,
        "shake_path_mm": [round(v * 1000, 5) for v in ground_path(frames, fps, SITE["peak_g"], SITE["hz"])],
        "pull_g": [round(v, 5) for v in sideways_pull(frames, fps, SITE["pull_g"])],
    }
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(steps)} sequential steps, {sum(bool(s.get('physics')) for s in steps)} physics checks")


if __name__ == "__main__":
    main()
