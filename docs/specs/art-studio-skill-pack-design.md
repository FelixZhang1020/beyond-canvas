# Art Studio Skill Pack — Design

Status: draft for the user's review. Companion documents: the
hackathon brief and the skills dossier written alongside it, research notes kept outside this
repository (research and numbers live there; this file states decisions).

## 1. Purpose

Build a children's art studio whose every feature is an Agent Skill in the NVIDIA
release format, run by a small harness on one DGX Spark with Step models. The
hackathon deliverable is the skill pack plus its evaluation evidence; the studio
web page is the demo of the skills working together.

Features: gentle feedback on a drawing; black-and-white sketch to 3D toy; painting
to animation; painting to walk-in scene; several drawings to a narrated storybook.

## 1a. Business scope

**User update:** add a local course Portfolio above the classroom, with a
profile for each course and access to its contents. This supersedes the one-off retention
decision below: originals, confirmed words, responses and completed creations are now
saved by course. Raw recordings and voice-reference caches remain temporary; no child
identity or individual growth profile is introduced. A standalone **Mark class ended** action
makes course content read-only. **Reopen course** restores editing in that same course,
including originals, confirmed words and saved opening context; new model work repeats
safety checks. Leaving or refreshing only releases the editor. See the current
[page contract](studio-page-contract.md) and
[implementation evidence](../measured/course-portfolio.md).

The following paragraphs preserve the earlier decision and its rationale.

Settled. These four answers rank the features and decide what the
software must not do.

| Decision | Answer |
|---|---|
| Customer | A children's art centre. One Spark per centre, sitting in the studio. |
| Operator | A teacher, during class. Not the child, and not a parent at home. |
| Hero layer | Layer one, the evaluation layer, both entrances. It is the hero not because the writing is good but because **it is the only layer that produces the child's own words and the child's own voice.** Everything layers two and three consume comes from here. |
| Session | One-off. Nothing about an individual child persists between visits. |
| Revenue | Undecided. The build commits to no model. |

**The value being sold.** In a class of twenty with one teacher, most children get
under a minute of individual attention on their work. The studio gives every child
a specific, warm response to what they actually drew, every time, without the
teacher leaving the child in front of them. That argument holds whichever revenue
model is chosen later.

**What the one-off choice removes.** No per-child identity, no stored history, no
growth tracking across months, and no guardian consent flow for storage, because
nothing is stored. Drawings live in memory for the length of one session and are
deleted afterwards. This is a large simplification and it makes the privacy claim
absolute: nothing is kept and nothing leaves the box. The cost is the "watch your
child grow" story, which the local box could support later without changing any
skill.

**What stays within a session.** A child usually makes several drawings in one
class, so multi-drawing features still work: today's four drawings can become one
storybook before the child goes home.

**Adopted scenarios, in build order.** Settled.

1. **One child, mid-class.** The teacher photographs a finished drawing and gets
   warm, specific feedback in seconds, with one open question to ask the child.
   This is the hero and must be excellent. Three behaviours belong inside it and
   are not separate features: a blank page or a photograph is refused kindly; a
   name or school written on the paper is never read back; a frightening subject
   is described warmly and judged not at all.
2. **The drawing moves, hangs on a wall, or stands up.** *Droppable, and droppable
   per output rather than all at once.* Four things one drawing can become; see
   section 5b.
3. **A session's drawings become a narrated story.** *Droppable.* Today's four
   drawings become one ordered, narrated book before the child goes home.

**三层结构.** Settled. The three scenarios are three layers, and the
entrance forks at the first one. Everything below the fork stays forked until the
third layer, where the distinction stops mattering.

| 层 | 素描 | 彩画 |
|---|---|---|
| 一 · 评价层（入口，人工选择） | Professional critique: 光影, 比例, 结构 | The child tells the story inside their picture; output is audio in their own voice |
| 二 · 动画层 | The form stands up as a 3D scene with a movable light and swappable materials | The drawing moves |
| 三 · 故事层（不再分类型） | Pictures and assets chosen from the two layers above, plus a story style and scene presets, become a page-turnable animated book narrated in the child's own voice | |

**This makes the layers a chain, not three parallel features, so the drop rule
changes.** Layer one cannot be dropped: it is the entrance and the only source of
the child's voice. Dropping layer two leaves layer three alive but static, a book
rather than an animated book. That degradation is clean and acceptable.

**Drop gates.** Scenarios 2 and 3 are commitments only until
their gate; after it they are cut without further discussion and the time goes to
the hero and to the fine-tune. Scenario 2 is cut if it is not running end to end
**four days after the Spark arrives**; scenario 3 is cut if it is not running **two days
after that**. Both gates sit between the Spark arriving and the fine-tune claiming the
machine a week after it arrives, so a slip cannot eat the highest-scoring work. The gates
are pinned to the fine-tune window rather than to the calendar: if the event moves, they move.

Why the gates exist: the only first-hand account of a placing team in this
hackathon records the pivot they credit for the result — 「把项目做成」比「把项目
做优秀」更重要, finishing beats polishing. That team shipped one feature with
three people. Seven skills, a fine-tune, an eval harness, governance tooling and
a container recipe in ten days is the failure mode they describe avoiding.

**Not adopted.** Photographing a whole class in one batch at pack-up. Running the
first scenario repeatedly covers it if it is ever wanted, so nothing is designed
against it now. The class-wide value argument still holds in the pitch.

## 1b. The event

Verified from Chinese sources; the evidence and the confidence level
behind each line are in the evidence audit, kept with the research notes. English
search does not reach this event: the North American NVIDIA Spark Hack Series is
a different competition family and none of its format, tracks or team sizes
apply here.

| Fact | Value |
|---|---|
| Name | NVIDIA DGX Spark 多模态 Agent 创意黑客松 |
| Organizers | NVIDIA 开发者社区 with 阶跃星辰 StepFun and 赞奇科技 XSUPERZONE |
| First edition | An earlier edition, with teams assigned by 随机组队 |
| Registration | scrm.nvidia.cn |
| Rules | Not published. The 赛事技术文档与工具包 carries the 评审标准 and 提交流程 and reaches entrants through the training camp at registration. |

**StepFun is a co-organizer, not a vendor whose model was chosen.** NVIDIA's own
training camp teaches 基于 DGX Spark 和 Step 3.7 搭建本地 Agent Team. The two-mode
design in section 7 is therefore the taught pattern executed harder, not a
workaround for a memory limit, and the pitch should say so.

**One precedent is known.** Spark Scroll, an illustrated-storybook generator
turning a text story into sequential panels, placed in the first edition. Its
input was text; ours is the child's own drawing. Section 13 item 4 carries what
that means for the demo. Reported by one participant, not by a winners list.

## 2. Constraints that shape the design

| Constraint | Consequence |
|---|---|
| No DGX Spark until the hosted unit arrives when the event opens; a Mac (M5 Pro, 64 GB) and API budget are available now | Two phases. Phase 0 develops against cloud APIs and the Mac; Phase 1 ports to the Spark. Every skill calls a named model slot, never a vendor directly. |
| Spark usable memory 108 to 119 GB; out-of-memory freezes the machine; loads can transiently cost 2× | A memory watchdog, fixed load order, unload-before-load, no swap. |
| Step 3.7 Flash at 4-bit is 105 GB and leaves no room for media models | Two modes: studio (small resident Step model plus media models) and director (Step 3.7 Flash alone). |
| Commercial children's product | Only commercially usable licenses; no photo persistence without guardian consent; the teacher chooses the 素描 or 彩画 entrance per class. |
| Ten build days | A working closed loop by day four; everything after is proof or polish. |

## 3. Model slots and the two profiles

Skills reference slots. A profile file resolves each slot to a provider and model.
Switching profile changes no skill code.

**Rewritten.** Every Phase 0 entry below was replaced in one pass, and
the reasoning for each lives on its own slot in `studio/profiles/`. Two rules now
govern the column: buy from StepFun wherever StepFun sells it, and make the
stand-in the same weights the box will load. Only the voice still breaks the
second rule, and it cannot be fixed — StepAudio 2.5 has no open weights.

**The prices in this table are per-token list prices, and one deployment no
longer pays them.** StepFun First buys every Step model on a
subscription, at `https://api.stepfun.com/step_plan/v1` rather than `.../v1`, so
its calls have no marginal cost and the ¥1.35 / ¥8.1 pair below does not apply
to it. The table's own profiles — `cloud` and `spark` — are untouched. What the plan
includes: [docs/guides/stepfun-plan-models.md](../guides/stepfun-plan-models.md).

**Decision: StepFun First is the only deployment.** The operator archived
API First and Local First at the same time; their profiles are kept for reference in
`studio/profiles/archive/`. Two consequences, stated before the decision was taken:
a machine with no GPU box can no longer start the studio (API First was its fallback),
and every class sends a child's recorded voice to StepFun for transcription (Local
First was the only deployment that kept it on owned hardware).

| Slot | Role | Cloud profile (Phase 0) | Spark profile (Phase 1) | Same weights? |
|---|---|---|---|---|
| vlm.studio | resident voice: feedback, ordering, story, sight checks | Step3-VL-10B GGUF Q4_K_M on the Mac via llama.cpp; `cloud` substitutes Qwen3-VL-8B so the writer never grades itself | Step3-VL-10B BF16 or FP8, tuned LoRA merged, 24 GB | yes, locally |
| vlm.director | teacher, eval judge, final polish | `step-3.7-flash` direct from StepFun (¥1.35 / ¥8.1 per M) | Step 3.7 Flash, UD-Q3_K_M — IQ4_XS does not clear the ceiling once the projector is counted | yes |
| image.edit | sketch cleanup and colorization; missing storybook pages | Step1X-Edit v1 via `zsxkib/step1x-edit` on Replicate — the deployment StepFun's own repo links to. NOT their API: StepFun is retiring the whole image line | Step1X-Edit v1 FP8, big slot, 34 GB measured peak | yes, pinned to v1 |
| mesh.fast | instant 3D toy | `camenduru/instantmesh` on Replicate | InstantMesh, 6 GB, resident | yes |
| mesh.premium | textured 3D toy for the pitch | nothing hosts Step1X-3D; the official Space is paused | Step1X-3D, big slot, 18.3 GB measured | box only |
| ~~video.scene~~ | **Deleted.** Section 5b rejects video diffusion on principle and section 07 of the scenario document lists it under 明确不做的事. This row contradicted 5b for a day, and the slot stayed in both profiles because of it | — | — |
| ~~rig.figure~~ | **Deleted.** `painting-to-animation` shipped and moves a drawn figure with no model at all, so nothing was left for this slot to serve | — | — |
| depth | painting to layered scene | not wired; nothing calls this slot | Depth Anything V2-Small, resident, 0.1 GB measured | untested |
| tts.studio | narration while the child waits | `stepaudio-2.5-tts`, voice `wenrounvsheng`, with the instruction field SiliconFlow has no equivalent for | Step-Audio-EditX, resident, 7.7 GB — cloning, emotion and a "child" speaking style | **NO** — StepAudio 2.5 has no open weights |
| tts.export | premium narration for the exported book | same model and a preset voice. Cloning is out of Phase 0: it needs a child's recording sent to a vendor and `transcribe.py` refuses | the same loaded Step-Audio-EditX, in cloning mode | **NO**, as above |
| speech.in | hearing the child | Whisper small q5_1 on the Mac, 0.18 GB | Whisper small q5_1, resident — added later, having been in no box profile at all | yes |
| safety.image | input filter | not wired; `studio-safety` borrows `vlm.director` at 8–11 s a drawing | ShieldGemma 2, resident, loaded first, 8 GB | no |

Provider errors, timeouts and rate limits are mapped to one error type by the slot
layer so gates treat cloud and local failures identically.

## 4. Components

1. Harness (Python). Scheduler, state machine, gates, append-only ledger, memory
   watchdog, mode manager. One process; skills run as subprocesses inside the base
   container on the Spark or directly on the Mac.
2. Skills (seven folders). Each has SKILL.md, scripts/, references/, assets/,
   evals/evals.json, skill-card.md, BENCHMARK.md, skill.oms.sig. Corrected:
   this list previously called for a second eval file in a separate
   "agentskills.io shape". There is no second shape. NVIDIA's catalog adheres to
   the agentskills.io specification and accepts evals at any of four paths —
   evals/evals.json, evals/*.json, eval/*.json, benchmark/evals.json — which is
   path flexibility, not a competing schema. One eval file per skill.
   **Where this stood.** Five of the seven have a folder that
   passes `evalkit.packaging`: studio-safety, art-feedback, sketch-to-3d,
   painting-to-animation and drawings-to-storybook (its prompts moved out of
   `studio/prompts/` into the folder at the same time). painting-to-scene has no code
   behind it — the classroom answers that it is not open yet — and
   studio-harness is `studio/core/harness.py`, driven by explicit Python, not a
   skill a model chooses. **Decided: both leave the claimed set.**
   The pack is five skills — studio-safety, art-feedback, sketch-to-3d,
   painting-to-animation, drawings-to-storybook — and the harness is the harness.
   Their rows in the contract table below are struck through, not deleted, so
   the reasoning stays readable. Signing: see the note under
   component 5.
   **Added later (operator): painting-to-figure is the sixth.** A colour
   painting also gets a free 3D toy figure, written by Step 3.7 Flash as simple
   solids and checked before any child sees it — the nearest the pack has come to
   §5b's 角色立起来, and a still toy, not a posable one. Paid walkable worlds
   (GPT-6 Astra) were decided at the same time for the hackathon showcase only, with
   the sample paintings — AI-made or the operator's own by the operator's ruling
   (see `docs/guides/deployment-versions.md`); no painting from a class
   goes to that service.
3. Studio page (single HTML file, vanilla JS). Upload, entrance choice, feature buttons,
   progress queue, GLB viewer, video player, book reader, ledger view for judges.
4. Evaluation harness. SkillEvaluator (Tier 1 to 3) with vlm.director as judge;
   SkillSpector; a rubric grader script for art-feedback; a three-way comparison
   runner (prompted big model, untuned small model, tuned small model).
5. Governance tooling. skills-ref validate, skill-card generator, model_signing with
   the team's key. No team key existed at first; the operator then
   decided the key lives on the development Mac, and the signing step and its
   verification are recorded in `docs/guides/skill-signing.md`.
6. Base container recipe (Phase 1 only). PyTorch 2.9, flash-attention wheel, ComfyUI
   with memory mapping disabled, StepFun llama.cpp fork, ms-swift, watchdog.

## 5. Skill contracts

| Skill | Input | Output | Gate (deterministic first, sight check second) | Negative eval cases |
|---|---|---|---|---|
| studio-safety | any image or text | allow / soften / block + reason; PII flags | classifier score under threshold; OCR finds no name or school text echoed downstream | adult photo; blank page; drawing with name and school; violent photo |
| art-feedback | which entrance (素描 or 彩画, chosen by the teacher); drawing photo; optionally the lesson intent and a transcript of the child speaking | 2 to 4 sentences plus one question; on 彩画 the child's story, on 素描 a technical read built around what the child found hard | rubric grader, fourteen rules, rule 6 scoped to the 彩画 entrance; banned-phrase lists; grounding check on the named dimensions | adult photo declined; blank page asks for a photo; scary theme described warmly without judging; any correction on the 彩画 entrance fails |
| sketch-to-3d | line-drawing photo | GLB + turntable PNG | file opens with trimesh; silhouette IoU against the sketch above threshold; sight check by vlm.studio | colored painting routed to painting skills; photo of a real object declined |
| painting-to-animation | painting photo, optional hint | MP4 | figure detected → rig path, else video path; clip length and resolution as requested; sight check: subject preserved, no new text | figure with missing limbs falls back to video path; blank page declined |
| painting-to-figure | colour painting photo | parts JSON — 3 to 140 solids, each a shape, place, size, turn and colour — drawn by an isolated viewer | numbers and colours only, bounds enforced; parts settled onto a base so no group hangs in the air (a tiny detail moves with its neighbour and can hover beside it); the preview sheet passes studio-safety; a look check by vlm.figure, taken twice and both must pass (same subject, the main characters' faces keep their eyes, nothing broken or upsetting; never asks for writing); one rewrite with the reason, then held back | sketch entrance refused; unreadable reply rewritten once; a figure that is not the painting's subject held back with a message, never shown |
| ~~painting-to-scene~~ | **Dropped.** Never built; the classroom answered "not open" and the page never showed its button. Was: painting photo → layered scene package (depth, layers, camera path) + preview MP4 | — | — | — |
| drawings-to-storybook | up to 8 drawings plus the assets they carry from the layers above, a story style and scene presets | page-turnable book, the child's own words, narration in the child's cloned voice | every drawing used once; order justified in the ledger; not one word of the child's language substituted; audio matches text | one drawing only (declines); mixed adult photos filtered; eight unrelated drawings become an anthology rather than a forced single story |
| ~~studio-harness~~ | **Dropped.** It is `studio/core/harness.py`, driven by explicit Python, not a skill a model chooses; its gates (one retry, then repair, then stop; resume from the ledger) are tested as the harness's own. Was: request from the page → plan, stage results, resumable ledger entry | — | — | — |

Every skill's SKILL.md gives one default per step, lists gotchas found during
evals, and stays under 500 lines with details in references/.

Frontmatter is a closed set and we do not invent keys in it. Corrected:
this paragraph previously had each skill declare its network, file
and shell needs as frontmatter fields. The specification defines `name` and
`description` as required and `license`, `compatibility`, `metadata` and
`allowed-tools` as optional, and nothing else; an invented top-level key does not
survive `skills-ref validate`. Those declarations go in `compatibility` (free
text, 500 characters) or `metadata` (arbitrary key-value), and the choice between
them is made once and applied to all seven. `name` must also match its own
directory name, which the seven current names already do.

Three levels decide what a skill costs. The `name` and `description` load at
startup and stay resident for every skill in the pack whether it fires or not, at
roughly 100 tokens each; the SKILL.md body loads on activation and is recommended
to stay under 5,000 tokens; scripts/, references/ and assets/ are read only when
needed. This is the structural reason the blank-page, name-redaction and
scary-subject behaviours live inside art-feedback rather than becoming skills of
their own: three more skills would be three more permanently resident
descriptions competing for trigger accuracy.

## 5a. The hero scenario: 我看到 → 我好奇 → 你来说 → 我听见了

Written from the operator's description of the job and refined with them.
This is the hero scenario and the most detailed part of the product.

> 就是不仅仅是评价画，而是引导孩子把自己画里的故事讲出来。那他今天上完课带走
> 的，就不止一张静止的涂鸦，而是属于他自己的故事、自己的心路历程。
>
> — the operator

That sentence is the product. Everything below serves it.

**The comment is not the product.** It is the opening move. The product is the
story the child tells about what is happening inside their own picture, in their
own words. The machine is a midwife, not a critic.

**What goes home changes.** Not a drawing with a machine's evaluation attached,
but the child's own story attached to their own drawing. The machine's comment
does not need to appear in it at all. A parent at pickup receives what their child
said, not what a model wrote.

**The concept underneath is a membrane between two worlds.** A child draws
something in the real world. In the machine it becomes a world with characters,
events and its own logic. That world turns around and asks the child a question.
The child answers out loud, in the real room. What they say crosses back and makes
the world more complete.

The point is not that a drawing becomes 3D or animated. That is one-way; it only
moves the picture onto a screen. The point is that the world reaches back and
changes what the child does in the real room: makes them speak, makes them go and
find something, makes them keep drawing.

### The four beats

| Beat | What happens | Why it is there |
|---|---|---|
| 我看到 | One specific observation. Not praise. | Buys attention and proves someone actually looked. |
| 我好奇 | One question, chosen for this drawing. | Opens the door this particular picture left ajar. |
| 你来说 | The child narrates. Thirty seconds to three minutes. | This is the product. |
| 我听见了 | The reply uses what the child just said. | This is where a child feels heard, not at the opening compliment. |

The fourth beat is the easiest to drop and the one that matters most. When it
lands, children usually add something they had not said yet. That addition is the
evidence that it worked.

### Inputs

| Input | Required | Note |
|---|---|---|
| 学生作品照片 · photograph of the work | yes | The only strictly required input. |
| 本节课的教学思路与目的 · the lesson's teaching intent | no, set once per class | The teacher enters it at the start of class, not per child. Lets the feedback connect the child's work to what was actually being taught. |
| 学生介绍自己作品的音频或视频 · the child describing their own work | no, per child | Two ways in. The teacher may supply a recording made earlier, or the machine's own question elicits it live, which is the design in the four beats. Either way it is transcribed to text first so the teacher can see what was heard and the transcript is auditable. The skill must be excellent from the photograph alone, because in a class of twenty not every child will speak. |

Transcription uses Step-Audio 2 mini, whose Chinese error rate is about 3.2% and
which is the sponsor's own model. Passing raw video to the language model is the
alternative and is rejected: it costs far more tokens and leaves no transcript
anyone can check.

**The child's own words resolve the hardest failure.** Without them the model
guesses what an ambiguous shape is, and guessing wrong tells a child their meaning
was not understood. With them, naming the shape is repeating the child, not
presuming.

### 视频要抽帧，不要整段送进去

Measured and recorded in `docs/measured/video-vs-frames.md`.
Step 3.7 Flash accepts video and does read more than one frame, but on three
large, one-per-second, unmistakable shapes it got the third one wrong. Sending the
same three frames as separate images was fully correct and cheaper. An animated
GIF is worse still: only the first frame is read at all.

So the video is never sent whole. Frames are sampled and sent as images.

**Why this matters more than it sounds.** Children point instead of naming. They
say 这里烧起来了, 那个是他哥哥, 这边不能停. A plain transcript throws all of that
away, because 这里 and 那个 carry no meaning without the gesture.

Frame selection is therefore aligned to the transcript's timestamps: a frame is
taken at the instant the child speaks a pointing word. That is more precise than
the whole video would have been, since it captures the hand at the moment the word
is said rather than hoping the model finds it.

### Dimensions to evaluate

画面具体内容 · 创作思路 · 故事情节 · 色彩搭配 · 构图 · 造型

Every response is positive in angle. Not every dimension appears in every
response; the feedback names the ones the work actually supports.

### 两个入口：素描 和 彩画

Settled. The system has **two separate entrances, chosen by hand**. The
teacher picks one when the class starts. There is no automatic detection: a
coloured-pencil study would fool a colour test, and the lesson already knows which
kind of class it is.

| | 素描入口 | 彩画入口 |
|---|---|---|
| What it evaluates | 光影, 比例, 结构, 技法 — professional critique | 画面内容, 创作思路, 故事情节, 色彩搭配, 构图, 造型 |
| Correction | **Expected.** A student drawing a plaster cast wants to know where the proportion slipped. Withholding it fails them. | **Never.** Correction here is harm. |
| What the child says | Reflection on their own process | The story inside their picture |
| What it produces | A technical read plus the child's own account of the hard parts | The child's story, in their own voice |

**This fork replaces the teacher's suggestion switch and the age split, and both
are deleted.** Whether to critique is decided by the kind of work, not by the
child's age and not by a toggle. A plaster-cast study is a technical exercise at
any age; an imaginative painting is not a technical exercise at any age.

**One stance holds on both entrances:** always positive in angle, 童真童趣 in
voice. On the 素描 entrance, positive framing means a correction arrives as
something to try rather than as something got wrong.

### 素描入口上的四拍

The four beats survive, but the second one asks a different question. A plaster
cast has no story, so 画里发生了什么 would be absurd. It asks about process instead.

| Beat | 彩画 | 素描 |
|---|---|---|
| 我看到 | A specific observation about the picture | A specific observation about the drawing: where the light turns, how a proportion sits |
| 我好奇 | 你画里正在发生什么事？ | 哪一块你改了最多次？ |
| 你来说 | The child narrates their story | The child says where the difficulty was |
| 我听见了 | The reply uses their words | The reply uses their words, and the technical read is built around what they found hard |

The point is the same on both: the child speaks, and is heard. On the sketch
entrance it is not a story but their own account of the struggle, which is exactly
what a teacher of technique most wants to know and least often has time to ask.

### 讲的是画里的故事，不是这张画

The whole design turns on two characters' difference.

| Prompt | What comes back |
|---|---|
| 跟我说说你的画 | A list. 这是龙，这是房子，这是太阳. |
| 你画里正在发生什么事 | A story. 龙刚飞回来，因为它家着火了. |

The first describes an artifact. The second enters a world. Only the second
produces 创作思路 and 故事情节, which are two of the six dimensions and are not
visible in any photograph.

### The craft: ask about the world, not the artifact

Choosing the one question this drawing makes possible is worth more than the
paragraph of feedback around it. Working patterns:

- Not 你画了什么, but 画里现在几点了.
- Events rather than objects: 刚刚发生了什么, 他接下来要去哪.
- The unseen: 画外面有什么, 谁没有被画进来. This class forces invention hardest.
- Inner state: 他现在在想什么.
- Before and after, because a picture is one frame: 他是怎么走到这里来的.
- The senses: 如果我站在这里，会听见什么声音.
- A problem, because conflict is the engine of story: 他好像遇到麻烦了.

The strongest form is a question asked **from inside the fiction**, by a character
in the drawing rather than by an adult: 我是那只鸟，我能停在你的树上吗. The child
is no longer answering a grown-up, and the guard drops. This is the oldest
technique in drama education and it is the third rung below.

### When the child says nothing, climb three rungs

Never repeat the same question. Make the door smaller.

1. **Open.** 这里发生了什么事？
2. **Two choices.** 他是刚到，还是正要走？ A child who cannot invent can still
   choose, and choosing usually starts them talking anyway.
3. **A character asks.** The bird in the drawing speaks. Almost no child refuses
   this, because they are not completing a task, they are answering something they
   made themselves.

### When the child is talking, stop talking

The failure is not silence. The failure is turning this into an interview. Ask one
thing, then get out of the way. Once a child is going, do not insert a single word.

### The world must actually change

This is the last beat and the easiest to lose. If the child says 龙的家着火了,
then the next thing the machine says must use that sentence, the world now
contains a fire, and the story that goes home uses the child's own words rather
than a polished rewrite.

The child has to be able to see that **because I said that, the world changed.**
Until that happens, this is only a talking report card.

### Worked examples

**Seven years old. A purple animal, a spiked sun, two figures holding hands.**

> **机器**：我看到你把这只动物涂成了紫色，太阳的光画成了尖尖的三角形，下面两个人手拉着手。他们刚刚发生了什么事？
> **孩子**：他们要去找他的妈妈。他妈妈丢了。这个是他哥哥，这个是他。他们走了很久很久。
> **机器**：所以你把这条路画得这么长，是因为他们走了很久吗？
> **孩子**：对！而且路上特别热，所以太阳画得很大。

The last line is the proof. Reflecting the child's words back made them add
something they had not said. The world now holds a search, a lost mother, a long
road and heat.

**Five years old. A tangle of orange lines nobody can identify. A stuck child.**

> **机器**：我看到很多橙色的线，绕了一圈又一圈，角落里还有三个绿点。这里正在发生什么事？
> **孩子**：……
> **机器**：这些橙色的线，是在转圈圈，还是在往前跑？
> **孩子**：转圈圈。
> **机器**：转得快，还是慢？
> **孩子**：很快很快。快到停不下来。
> **机器**：什么东西转得这么快，停都停不下来呀？
> **孩子**：是风。风把绿色的豆子吹跑了。

Two rungs, and the machine never once guessed what the lines were.

**Eight years old. A dark creature with red eyes and pointed teeth.**

> **机器**：我看到它有两只红色的眼睛，牙齿是白色的三角形，身体的颜色很深。它住在什么地方？
> **孩子**：住在山洞里。它其实不吃人。
> **机器**：那它吃什么？
> **孩子**：吃石头。它牙齿这么尖，就是为了咬石头。别人都以为它很坏，其实不是。
> **机器**：原来这些尖牙是用来咬石头的。那有人知道它其实不坏吗？
> **孩子**：只有我知道。

No 好可怕, no 你今天怎么了, no suggestion to draw something happier. Any of those
and 只有我知道 never gets said.

**Four years old. The character asks, which is the third rung.**

> **机器（用画里那只鸟的声音）**：我是你画的那只鸟。我可以停在你的树上吗？
> **孩子**：可以。但是不能停最高的那根，那是给妈妈鸟的。
> **机器（鸟）**：妈妈鸟去哪里了？
> **孩子**：她去找虫子了。她一会儿就回来。

A four-year-old cannot tell a story on request. A four-year-old can answer a bird.

Across all four the machine speaks three or four times. Everything worth keeping
is the child's own language: the long road, the wind that cannot stop, the teeth
for biting stones, the branch saved for the mother bird. No model writes those.
It only draws them out.

### 孩子自己的声音，讲他自己的故事

The book that goes home is narrated in the child's own voice.

**The voice sample is free.** Beat three already records the child telling the
story. That recording is the reference audio. No separate session, no extra
burden on the teacher, no child asked to read anything aloud for a machine.

**Why clone at all, rather than replay the recording.** Raw speech is disfluent,
out of order, and interleaved with the machine's questions. The book wants one
clean read of the assembled story. Cloning lets the child's own voice read the
tidied version.

**Tidying is not rewriting.** Remove the 呃 and the false starts, put events in the
order the child established, and stop. Not one word is substituted. This is rule
14 and it applies here most sharply, because a synthetic voice makes a rewrite
sound like the child said it.

**Cost.** A cloning model is roughly 4 to 6 GB resident on top of the working set,
and a two-minute narration is about twenty seconds of compute. It is the cheapest
component in the workflow.

**Three constraints, all mandatory.**

1. **The cloned voice may only speak words the child actually said.** Not a
   technical limit but a product rule, and it closes off misuse entirely.
2. **The voiceprint never persists.** Cloned at the end of class, used, destroyed,
   consistent with the one-off session decision.
3. **This needs its own guardian consent.** Storing a recording and synthesising a
   child's voice are different in kind, not degree. "Nothing is stored" covers the
   first and does not cover the second.

**It is also the strongest hardware argument in the product.** A child's voiceprint
is the most sensitive thing in that building. Cloning it on a box that cannot reach
the network, and destroying it before the next class, is a thing that would alarm
every parent in the room if it were a cloud service.

### Consequences for the rubric

| Rule | Change |
|---|---|
| 4, presumes nothing | A claim is no longer presumptive when the child said it. The transcript, when present, is supplied to the check. |
| 6, corrects nothing | **Applies on the 彩画 entrance only, and there it is absolute.** No switch, no age condition, no exceptions. On the 素描 entrance the rule does not apply at all, because critique is the whole exercise. |
| 7, never judges realism | Settled with the operator when the fork was built: applies on the 彩画 entrance only, like rule 6. Its phrase list (比例不对, "out of proportion") is the vocabulary of a sketch critique, so on 素描 a correct read would fail it. |
| 10, sentence length | Loses its age bands. One short-sentence limit for everyone. |
| 11, new: serves the lesson | When a lesson intent was given, the feedback connects the child's work to it. Skipped when no intent was supplied. |

Rules 1 to 11 govern what the machine says. Three more govern the loop itself.

| Rule | What it checks |
|---|---|
| 12, the question enters the world | The question asks about events, characters, the unseen or the senses inside the picture, not about the artifact. 你画了什么 fails. **On the 素描 entrance the question enters the process instead** (哪一块你改了最多次), since a plaster cast has no story; a story question fails there. Settled with the operator. |
| 13, the reply uses the child's words | After the child speaks, the machine's next line must reuse their own language. A reply that could have been written before they spoke fails. |
| 14, the machine never tells the story | No story content the child did not supply. The moment the machine offers a better version, the child's version dies. Their story is also never corrected: if the child says the sun is angry, the sun is angry. |

## 5b. 第二场景：画会动、画上墙、画立起来

One drawing, four possible outputs. They share an input and nothing else, so each
one lives or dies on its own at the drop gate rather than as a group.

| Output | What it is | Needs a GPU |
|---|---|---|
| 会动的画 | The child's own lines move. A figure is rigged and walks; anything else drifts, sways, grows or enters. | Light |
| 抽象挂画 | A framed abstract piece derived from the drawing, made to hang in an ordinary home. | Medium |
| 素描立起来 | A black-and-white line drawing becomes a 3D model that turns on screen and could be printed. | Heavy |
| 角色立起来 | The character inside the drawing becomes a posable 3D figure. | Heavy |

### 不用视频扩散模型，这是原则问题不是成本问题

> **Decided later: the clip stays.** Operator decision, reversing this
> section. The shipping product does what it forbids — `video.animation`
> resolves to Wan 2.2 (the 5B on the 4090, the A14B hosted), and 让画动起来
> makes a short diffusion clip from the original beside the still Klein pose.
> Both were watched through the page (a still in 43 s, a clip in
> 288 s on the 4090 or 631 s hosted). The three arguments below were read again
> and the decision went the other way on each: the strokes argument is answered
> by the original never leaving the screen and the clip being labelled as
> generated, not as the child's work; the two-second argument was written for
> a hero scenario (龙飞走了 → the dragon flies) that this product does not
> stage — the teacher asks for the clip after the talk, not during it; and the
> choreography route the third argument prefers was never built, and nothing in
> the walk needed it. What survives of this section is the rule that the
> original is never replaced and the child's words are never rewritten; the
> ban on diffusion does not. The text below is kept as the argument that lost.

A video diffusion model redraws the child's work. What comes out is inspired by the
drawing; the child's actual strokes are gone. For a product whose whole claim is
*this is your work, your story, your words*, that is a betrayal at the pixel level.

Rigging plus programmatic animation moves the lines the child actually drew. Every
pixel on the screen came off their paper.

**The second reason is decisive on its own: it has to be instant.** Diffusion takes
one to fifteen minutes. Beat five of the hero scenario requires the child to say
龙飞走了 and see the dragon fly within about two seconds. At five minutes the child
has left and the moment is gone. Programmatic animation is not a cheaper
compromise; it is the only thing that makes the membrane work in real time.

**The third reason is what the model does instead, and it is the best part.** The
model stops generating pixels and starts writing choreography: which layer moves,
when, how far, in what order, driven by the child's own sentences. 他飞回来了
becomes the dragon layer entering from the right over 1.2 seconds. That output is
structured, checkable, gateable and deterministic to execute, which is a far better
account of an agent completing a task than calling a video model.

### 抽象挂画是唯一允许「重新画」的一件事

Every other output preserves or derives from the child's actual marks. This one
deliberately makes something new: it has to look good framed above a sofa, in a
home whose décor nobody has seen.

So it carries its own definition, and the wording matters to the product's
integrity: **it is not "your drawing", it is "a piece grown out of your drawing".**
The original still exists on paper. The two coexist and neither replaces the other.

The composition and palette are derived from the child's own structure and colours
rather than a style being applied over the top. That is the idea worth taking from
the reference the operator supplied, whose own licence rules out using its code.

**Commercially this is the first output a parent would actually pay for.** A moving
drawing and a storybook are things parents enjoy. A framed abstract piece derived
from their own child's work, that suits their living room, is a physical object
with a price on it. Section 1a records the revenue model as undecided; this is
likely part of the answer.

### 素描立起来：两个形体都要，并排放

Settled. The sketch entrance produces **both** forms, side by side under
the same light.

| | 他画的那个形体 | 正确的形体 |
|---|---|---|
| Where it comes from | Reconstructed from the child's own drawing | Modelled once, in advance |
| Risk | High. Image-to-3D from a pencil drawing is unproven, and none of the candidate tools has ever been tested on this hardware. | None. It is an asset, not an inference. |
| What it teaches | What they actually drew, seen in the round, with their own errors made three-dimensional | What the light really does on that form |

**The trick that removes almost all the risk from the right-hand column.** An art
centre draws a fixed set of objects. The plaster cubes, spheres, cones and busts
are the same ones every term. Model that set once and the correct form needs no
reconstruction, no ML, and no ARM compilation. Relighting and material swapping
are then ordinary rendering that runs in a browser.

So the feature degrades cleanly: if reconstruction of the child's form fails, the
correct form with a movable light is still a teaching instrument on its own.

**Materials.** 石膏, 木头, 大理石, 玻璃. The same form under different surfaces is
the thing a sketch teacher struggles to explain in words, and it is the reason
this is an instrument rather than a toy.

### 两个 3D 输出把 GPU 论据带了回来

Turning a sketch into a mesh, and turning a drawn character into a posable figure,
are the heaviest jobs in the product. Earlier drafts justified the hardware with
video generation; dropping video removed that. These two restore it, and on better
grounds, because the work is something the product genuinely needs rather than
something chosen to look demanding.

### Open until the survey lands

Which projects serve each of the four, their licences for commercial use, and
whether any of them build on ARM with a Blackwell GPU. Meta's AnimatedDrawings has been
archived and only handles roughly humanoid figures, so a second path
is needed for everything that is not a person, and a maintained successor may not
exist.

## 6. Data flow

request → studio-safety → studio-harness plan → skill stages, each: run → gate →
ledger append → page update → next stage. Failure at a gate: retry once with the
same inputs, then repair (vlm.studio proposes a change to the input or parameters),
then stop with a friendly message. Every decision is a ledger line with stage,
inputs hash, outputs path, gate result, tokens, wall time, memory before and after.

## 7. Modes and memory (Spark profile)

Studio mode resident set, loaded in this order at boot: safety.image 8 GB,
vlm.studio 24 GB, mesh.fast 6 GB, tts.studio 5 GB, depth 1 GB. Fixed total
44 GB. One big slot of up to 28 GB holds image.edit, mesh.premium or
tts.export, one at a time, unload before load. Peak 72 GB.

Revised twice over. Deleting video.scene and rig.figure took 16 GB
out of the resident set; the remaining sizes were then corrected against the
files themselves in `docs/measured/model-sizes-measured.md`, and
tts.export stopped being a rotating occupant because it is the same CosyVoice 2
that serves tts.studio and is already resident. The figure the watchdog enforces
is unchanged at 90 GB; what changed is how much room is left under it.

Director mode: unload everything, load vlm.director (109 GB), run the queued
director jobs (teacher data, eval judging, story polish), unload, restore studio
mode. Never triggered while a child session is active. The watchdog refuses any
load whose expected footprint plus the 2× transient would exceed 90 GB.

Cloud profile: no mode switching; director jobs go to the API immediately. Mode
switching logic is exercised on the Mac with fake model sizes so the state machine
is tested before the Spark exists.

## 8. Fine-tuning pipeline

1. Now until the Spark arrives: generate feedback for the user's scanned drawings and 1,000 to
   3,000 drawings from Meta's Amateur Drawings set using vlm.director under the
   rubric; two reviewers accept, edit or reject in a small web form; edits become
   chosen-versus-rejected pairs.
2. Two days on the Spark, from a week after it arrives: LoRA on Step3-VL-10B with ms-swift in director-mode
   memory (big model unloaded), then a three-way eval; swap the tuned model into
   vlm.studio only if its rubric pass rate is within five points of the big model.
3. Fallback: Qwen3-VL-8B with the same data and scripts; one config line changes.
4. Roadmap: preference tuning; a LoRA on Step 3.7 Flash on rented Hopper GPUs.

## 9. Evaluating both modes before the Spark exists

Cloud profile can measure everything about quality and nothing about latency or
memory. Quality metrics per skill: rubric pass rate, deterministic gate pass rate,
sight-check pass rate, SkillEvaluator's five dimensions, tokens per request. The
studio-versus-director comparison in Phase 0 is therefore "small Step voice on the
Mac versus big Step model via API" on the same eval sets.

**The comparison NVIDIA actually asks for.** The three-way model
comparison above answers a question about models. NVIDIA's bar for a verified
skill is about the skill: trigger accuracy, task completion and token efficiency,
validated by a live A/B against the same task run *without* the skill. That run is
not in the plan above and it is the one that argues the pack earns its place, so
it is added per skill: the same eval set, once with the skill installed and once
with the model working from the bare request. Cheap on the cloud profile, and the
result is the evidence a judge can be shown. Latency, throughput,
memory and mode switching are measured on day zero on the Spark and replace the
estimates in the dossier.

Day-zero benchmark list: memory after boot; vlm.studio tokens per second; one
image.edit run; one mesh.fast run; one mesh.premium build attempt; ten
studio-to-director-and-back switches without a freeze. The video clip that stood
in this list was removed with the slot.

## 10. Error handling and recovery

Provider or model failure: retry with backoff, then degrade (premium slot to fast
slot, tts.export to tts.studio, video path to rig path), then stop with a message a
child can read. Memory watchdog trip: refuse the request with words a child can
hear, rather than loading and freezing the box. Safety block: never explained to
the child in detail; the parent view shows the reason code, and `unsafe` is a
separate verdict from `block` so that an image which would harm a child is not
filed as a photograph of a room.

**Resume, corrected.** This section said a restart reads the ledger
and resumes. It cannot, and the reason is section 1a rather than a bug: the
session lived in memory, the drawings were deleted when the class ended because
nothing is kept, and the ledger lines went with them. A one-off session that
keeps nothing has nothing to resume from. What the ledger does protect is a
repeat WITHIN a live class — the same request asked twice skips the stages that
already passed — and that is the case that actually happens.

## 11. Testing

Unit: gates, ledger, watchdog arithmetic, mode manager (with fake model sizes).
Evals: every skill's eval file, run through SkillEvaluator and the rubric grader,
with negative cases, on both profiles, plus the with-skill versus without-skill
A/B from section 9. Integration: the day-four closed
loop on the cloud profile, then on the Spark. Soak: ten mode switches and a
two-hour queue on the Spark. Human panel: thirty to fifty drawings scored by
parents or teachers to confirm the rubric grader agrees with people.

## 12. Repository layout

```
studio/            harness, slots, profiles/{cloud,spark}.yaml, watchdog, page
skills/<name>/     SKILL.md scripts/ references/ evals/ skill-card.md BENCHMARK.md
evalkit/           rubric grader, three-way runner, converters between eval shapes
finetune/          teacher generation, review form, ms-swift recipes
container/         base image recipe for the Spark
docs/              this spec, the plan, measured numbers
```

## 13. Open items

1. Sponsor models on stage: resolved. The real rubric is not public
   but it is not absent either — it travels in the 赛事技术文档与工具包 and reaches
   entrants at registration (section 1b), so it arrives rather than being found,
   and no further searching will produce it. Until it does, the weights used for
   planning are a stand-in: a reused NVIDIA China rubric scoring 技术创新 30,
   项目完成 15, 应用价值 20, 团队协作及演示 20, 开发难度 15, with no line for which
   vendor's model was used, and one sibling hackathon gave bonus points for
   choosing an alternative model. Replace them on the day the packet arrives and
   re-check item 4 against the real numbers. Decision, unchanged by the above:
   Step 3.7 Flash and the tuned Step3-VL-10B are the Step story and are
   mandatory; Step1X-3D ships only if the day-zero build works; Step-Audio-TTS-3B
   is dropped unless its weight license is confirmed; Wan 2.2, Qwen-Image-Edit
   and InstantMesh stay as the practical media models, stated openly on the
   slide.
2. The product rule for dark or scary drawings: draft is "describe warmly, do not
   judge the theme, keep the open question"; the user confirms or changes it.
3. Guardian consent for the scanned drawings used in the demo and the teacher set.
4. **Nothing in this spec earns 团队协作及演示, which is 20 of the 100 points.**
   Mapping the other four criteria to the build gives 技术创新
   30 to the LoRA and the three-way comparison, 应用价值 20 to the gentle-feedback
   argument, 项目完成 15 to the day-four closed loop and 开发难度 15 to the memory
   watchdog and mode switching. The fifth has no owner. Two halves to answer
   separately. **Demonstration:** who presents, for how long, live or recorded,
   and what the judge sees in the first ten seconds — which matters more than
   usual here, because a picture-book generator already placed in an earlier
   edition, so the demo has to show a real crayon drawing entering the system
   rather than pictures coming out of it. **Collaboration:** the first edition
   used 随机组队, random team assignment. The ten-day plan assumes one builder who
   already holds the design. If teammates are assigned, the plan needs a division
   of labour and this criterion needs evidence of it. Confirm the format before
   the build order is locked. Caveat carried from the research: the weights above
   are from a reused NVIDIA China rubric and are not confirmed for this event —
   but every hackathon scores the demo, so the gap is real whatever the numbers.

5. **NVIDIA's safety model for `safety.image`'s Spark plan.** Opened later: Nemotron-3-Content-Safety,
   with a policy written by NVIDIA's `nemotron-policy-generator`, as the first check inside `studio-safety`
   at the entry and the exit, in place of the ShieldGemma 2 planned in section 3. Built into `studio-safety`
   and measured on the hosted Spark with NVIDIA's stock rules (operator's decision); not yet switched on in
   any classroom profile. Measured: `docs/measured/nemotron-safety-on-spark.md` and
   `docs/measured/safety-model-in-class.md`.

6. **The rebuilt hall must work, not only look right.** Opened later: three checks join the
   from-nothing hand-over gate — built like a real timber frame (frame census and column strength),
   stands under real loads (snow and slenderness in the column check, and a shake), and an advisory
   engineer's review by an NVIDIA Nemotron model reading the numbers. The first two are in the gate; the
   review is the operator's, after hand-over (operator). The checks:
   `skills/hall-carpenter/references/method.md`; the first hall through them:
   `docs/measured/rebuild-under-the-stricter-gate.md`.

## 14. Not in scope

Removed by the one-off session decision: per-child identity, stored drawing
history, growth tracking across visits, and any guardian consent flow for
storage. The interface keeps one session in memory and forgets it.

Removed by the art-centre decision: a consumer mobile app, a parent-facing
account, and printing or fulfilment of physical keepsakes.

Out of scope regardless: real-time voice conversation, cloud multi-tenant
hosting, formal regulatory sign-off, and a LoRA on Step 3.7 Flash itself.
