"""Does the 'explain one visible choice and its effect' instruction cost replies?

Same drawing, same opening, same child sentence, same grader; one variable: the
three-sentence instruction appended to the colour reply prompt.
Five real colour drawings, three tries per arm, first attempts only. Nothing in
the repository is changed; the trimmed arm is built in memory.
"""
import sys, json, time, concurrent.futures as cf
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills/art-feedback/scripts"))
from studio.env import load_dotenv
from studio.deployments import build_runtime
from evalkit.rubric import run_rubric, RED_LINES
import feedback as fb

START = "When connecting their words to the picture, explain one visible choice"
END = "Use everyday words and keep the existing sentence limit."
CASES = [
    ("Weixin Image_20260903223101_100_645.jpg", "小木屋里住着一个爷爷，河水结冰了他就去山上砍柴"),
    ("Weixin Image_20260903223101_102_645.jpg", "这是我的猫在过生日，天上放烟花，蛋糕是给它的"),
    ("Weixin Image_20260903223101_104_645.jpg", "粉色的狗狗会飞，它飞过城堡去找黑猫"),
    ("Weixin Image_20260903223101_108_645.jpg", "红色的车在追救护车，因为里面有我的朋友生病了"),
    ("Weixin Image_20260903223101_110_645.jpg", "天上的鱼会飞，它们在找下面的马和绵羊玩"),
]
TRIES = 3

def one_case(name, child_said):
    clients = build_runtime("stepfun").clients
    studio, director = clients["vlm.studio"], clients["vlm.director"]
    settings = fb.ClassSettings(entrance="colour", language="zh")
    image = str(ROOT / "Image Sample/Color Artwork" / name)
    uri = fb.to_data_uri(image)
    opening = fb.write_feedback(image, settings, studio).strip()
    full = fb.build_reply_prompt(settings, opening, child_said)
    a, b = full.index(START), full.index(END)
    trimmed = full[:a] + full[b:]
    lines = [f"## {name}\n   opening: {opening[:120]}\n   child: {child_said}"]
    tally = {}
    for label, prompt in (("WITH", full), ("WITHOUT", trimmed)):
        passed = 0
        for i in range(TRIES):
            for attempt in range(6):
                try:
                    text = studio.chat(prompt, [uri]).text.strip()
                    report = run_rubric(text, entrance="colour", image_data_uri=uri, client=director,
                                        child_said=child_said, lesson_intent="", opening=opening)
                    break
                except Exception as error:
                    if "429" not in str(error) or attempt == 5:
                        raise
                    time.sleep(20)
            bad = [r for r in report.results if r.status == "fail"]
            crossed = [r.rule for r in bad if r.rule in RED_LINES]
            ok = not crossed and report.pass_rate >= 0.8
            passed += ok
            lines.append(f"   {label} [{i+1}] {'PASS' if ok else 'FAIL'} red={crossed} :: {text}")
            for r in bad:
                lines.append(f"        rule {r.rule} ({r.name}): {(r.evidence or '')[:140]}")
        tally[label] = passed
        lines.append(f"   == {label}: {passed}/{TRIES}")
    return name, tally, "\n".join(lines)

def main():
    load_dotenv()
    totals = {"WITH": 0, "WITHOUT": 0}
    with cf.ThreadPoolExecutor(max_workers=1) as pool:
        for name, tally, text in pool.map(lambda c: one_case(*c), CASES):
            print(text, flush=True)
            for k in totals: totals[k] += tally[k]
    n = TRIES * len(CASES)
    print(f"\n=== TOTAL  WITH the instruction: {totals['WITH']}/{n}   WITHOUT it: {totals['WITHOUT']}/{n}", flush=True)

if __name__ == "__main__":
    main()
