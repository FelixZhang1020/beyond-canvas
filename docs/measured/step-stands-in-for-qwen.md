# Step 3.7 Flash stands in while Qwen is away

Qwen3.6 on the Spark writes the class's chat, judges it and screens the drawings, and it steps aside while
the Spark makes a Wan 2.2 clip: about eighteen minutes for the clip and four more to load again. Since the
operator moved every chat slot to Qwen, nothing stood in during that time, and a class whose teacher started a
Spark clip had no chat until Qwen was back. The operator asked for StepFun to take the conversation over
meanwhile, and this records the check.

## What was built

A `vlm.standin` slot in `studio/profiles/stepfun.yaml` (Step 3.7 Flash on the subscription, reasoning effort
low, 12,000 tokens), and `StandIn` in `studio/providers/frontvoice.py`: the first model is asked, and if it
gives no answer the stand-in is asked the very same thing. `studio/core/deployments.py` puts it behind every
Qwen slot a person waits for: the studio writer, the rule judges, the drawing's screen, the teacher review and
the creation drafts. NVIDIA's second look stays outside it, so the door and the way out keep their second
reader; the clip's wait for Qwen before its frames are screened still reaches Qwen's own client; a teacher's
cancel is raised as it came, never handed to the stand-in; and the slot's settings still read as Qwen's. In an
ordinary class the stand-in is never called.

## How it was checked

On the standard studio, in a colour course made for it: a sample drawing was added and Qwen wrote its opening
(2.2 s). Then Qwen was paused exactly as the media service pauses it for a clip: its pause flag written with the
media service's own process id and the container stopped, which the keeper honours until the flag goes. With
Qwen down, a child's answer was sent, a second drawing was added through the door, and its opening was asked
for. Then the flag was removed and the keeper loaded Qwen again.

| Step, with Qwen down | Who answered | Wall time | Rubric |
|---|---|---|---|
| The reply to the child's answer, written and judged | Step 3.7 Flash, the writer and three judges | **25.2 s** | 100 %, clean |
| The second drawing's screen at the door | Step 3.7 Flash's four verdicts, then NVIDIA's second look | **4.5 s** | allow, second look clear |
| The second drawing's opening, written and judged | Step 3.7 Flash | **29.9 s** | 100 %, clean |

The studio's log says each hand-over by kind: `qwen3.6-35b-a3b gave no answer (ModelUnavailable);
step-3.7-flash stands in`, once for the writer and once per judge. For comparison, the same reply with Qwen
answering takes about 4 s (`docs/measured/qwen-judges-the-class.md`), and before the judges moved to Qwen a
checked reply through Step took 40 to 80 s; today's 25 s is the writer at about 13 s and the judges, asked
together, at about 12 s.

## A real Spark clip, with the clip open to teachers again

After the check above the operator reopened the Spark's own clip to teachers (`closed_to_teachers` left
`video.animation` in the profile) and asked for a real one. In a colour course made for it, with Qwen's
opening already written, the teacher's choice was set to the Spark's Wan 2.2 and the clip started at 18:38.

| Moment | What the node did |
|---|---|
| 18:38:17 | The media service set the loaded TRELLIS.2 aside, then at 18:38:22 Qwen; NVIDIA's reader stayed |
| 18:38 to 18:56 | The clip was made in its own container: **92.3 GiB in use at its peak** (the last minute), 89 for most of the run, swap never above 1.1 GiB, the reader in every 10-second sample |
| 18:40:30 | A child's answer sent mid-clip: Step wrote and judged the reply in **22.6 s**, 100 % clean |
| 18:42:57 | A second answer: Step, **14.3 s**, 100 % clean |
| 18:56 | The clip done; the keepers took the lock in turn, TRELLIS.2 first (loaded 18:57:33), then Qwen |
| 19:01:17 | Qwen answering again; the clip's frames, which wait for Qwen rather than go to Step, were screened by it at once |
| 19:01:24 | The clip passed: safety pass, second look clear, clip check pass; 1,390 s from the request to the record, the page's own count 1,281 s from the start of making |

So a teacher who starts a Spark clip now waits about 23 minutes for it, and the class's chat answers throughout:
in about a second from Qwen until the clip takes its memory, in 15 to 25 s from Step while it is away, and in
about a second again once Qwen is back.

The description the clip is made from was written by Qwen before the clip (one draft rejected by the review,
the second passed), and its request took about two minutes to reach the studio through the relay, which the
page shows as 正在提交任务; it is not stuck.

## What this does not cover

- The reply times are a few samples, on an idle subscription in the evening.
- The Send button under the console chip, seen while driving the page at 1440 and 1568 pixels wide, is a page
  matter and not the stand-in's: the form was submitted by its own button from script.
