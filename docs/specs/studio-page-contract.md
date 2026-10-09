# Beyond Canvas studio page contract

Status: proposed by the page; the harness implements it. Companion to the
design record (`art-studio-skill-pack-design.md`, sections 4, 6 and 10).

The studio page is one HTML file in plain JavaScript, served by the harness. It holds one class
session in memory and releases it when the teacher ends the class. Since the user's
Portfolio request, the server separately retains local course history. It never talks to a model or a
provider; it talks to the harness through the routes below. A mock transport inside the page
implements the same shape so the page runs with no harness at all.

Status at the first classroom integration: feedback, sketch reconstruction, Klein still poses,
and original-artwork storybooks run through the classroom. Local preset speech is optional
and enabled by the integrated launcher. Walk-in scenes remain unavailable.

## Routes

| Method and path | Body | Returns |
|---|---|---|
| `GET /api/health` | | `{ok, profile, mode, skills: [], listening: bool, speech: {available, local, model, voices, default_voice}}` |
| `POST /api/session` | `{language: "zh"|"en", lesson_intent?: string, entrance: "sketch"|"colour", title?: string}` | `{session_id, course_id}`; creates an open saved course |
| `DELETE /api/session/{id}` | | `204`; idempotently releases the editor, without changing the course's ended status |
| `POST /api/session/{id}/drawings` | multipart `image` (JPEG or PNG) | `{drawing_id, url}` |
| `DELETE /api/session/{id}/drawings/{drawing}` | none | `204`; deletes the drawing for good, from the class and the Portfolio, with every result made from it alone. `400` with `code: drawing_busy` while a request for it is unfinished, `code: in_book` when a book shares it; `409` once the course has ended |
| `POST /api/session/{id}/heard` | multipart `audio` (16 kHz mono PCM WAV) | `{text, language}` |
| `POST /api/session/{id}/requests` | `{skill, drawing_ids: [], options: {}}` | `{request_id, plan: [{stage, skill}]}` |
| `GET /api/requests/{id}/events` | | server-sent events, one `stage` event per transition, then `done` |
| `GET /api/session/{id}/ledger` | | `{lines: [LedgerLine]}` |
| `PATCH /api/session/{id}` | `{language?, lesson_intent?}` | `204`; updates existing conversations; refuses during active work |
| `PATCH /api/session/{id}/drafts` | `{drafts: {drawing_id: text}}` | `204`; stores answer drafts separately from confirmed words for the current editable course; at most 100 entries and 10,000 characters per entry; rejects foreign drawings and stale/closed editors |
| `POST /api/session/{id}/speech` | `{text: string (1–400 characters), voice?: string}` | NDJSON `format`, `pcm` (base64 PCM16 mono), `done`; or `error` |
| `DELETE /api/session/{id}/speech` | | `204`; cancels current speech |
| `DELETE /api/session/{id}/requests/{request}` | | `204`; stops subsequent stages and late output |
| `GET /api/session/{id}/samples` | | `{items: [{id, url, thumbnail_url}]}` for the class entrance |
| `GET /api/session/{id}/samples/{sample}` | `?thumbnail=1` optional | normalized JPEG from the local sample library |
| `GET /api/courses` | `?q=&entrance=&offset=` | `{items, total, next_offset}`; newest first, 24 per page |
| `GET /api/courses/{id}` | | course profile, original drawing URLs and lightweight activity summaries |
| `POST /api/courses/{id}/complete` | `{}` | `204`; explicitly mark ended, block content writes and release its editor |
| `POST /api/courses/{id}/edit` | `{}` | `{session_id, course}`; restore an open course in a fresh editor; `409` if ended |
| `POST /api/courses/{id}/reopen` | `{}` | `{session_id, course}`; explicitly reopen the same course and restore its editor |
| `PATCH /api/courses/{id}` | `{title}` (1–120 characters) | `204`; rename the saved course |
| `GET /api/courses/{id}/drawings/{drawing}` | `?thumbnail=1` optional | saved original or thumbnail, still available after class ends |
| `GET /api/courses/{id}/activities/{activity}` | | `{outputs, ending, artifact_id}`; exact saved result, no inference |
| `PATCH /api/courses/{id}/activities/{activity}/ending` | `{text}` (1–2000 characters) | `204`; save the teacher-confirmed story ending |
| `POST /api/courses/{id}/speech` | `{text, voice?}` | local preset speech for an existing saved course, same framing and bounds as session speech |

`health.portfolio` advertises the configured local course store. Standard `studio.serve` enables
it at `.studio/portfolio.sqlite3`; an embedded Classroom may omit it for ephemeral use/tests.
`health.course_lifecycle` additionally advertises explicit completion/reopening and write guards.
The page refuses to start a purportedly saved class against an older HTTP service that lacks either flag.
Course metadata, artwork and outputs are persisted before success is acknowledged. Completed
outputs include `artifact_id`; large mesh/PNG payloads load only when a result is opened.
Confirmed words remain archived even when the following generated reply fails its quality gate.
Raw recordings, speech caches and hash-only diagnostic ledgers are not part of the Portfolio.

`course.id` is durable; `session_id` identifies only the current editor. Restoring a course gives
it a fresh editor ID and releases any previous editor for that course. Profile reads expose
`active` and `active_session_id`; `ended_at` alone means the teacher marked it ended. Inactive
open courses remain editable. Refresh, pagehide, switching and server shutdown never set `ended_at`.
Closed-course writes (name, settings, artwork, confirmed words, results and endings) are checked
inside the same SQLite transaction as the write and return `409` with `code: "course_closed"`.
Released editor URLs return `404` for editing operations. Reopening does not reactivate old editor
IDs or cancelled model requests. Read routes, result viewers, exports and archived speech still work.
Restoration recovers originals, confirmed transcripts and opening context, but not cached safety
verdicts or unconfirmed drafts; new model work repeats the normal safety checks.


`skill` is one of `art-feedback`, `sketch-to-3d`, `painting-to-animation`, `painting-to-figure`,
`painting-to-scene`, `drawings-to-storybook`. The harness runs `studio-safety` first for a drawing it has not screened
before, and reports it as a stage; a drawing already screened is not screened again, and the plan
says so rather than announcing a step that will not run.

`skills` in the health reply names what this studio actually serves. The page hides the controls
for everything else, because a button that always answers "that part is not open yet" is worse
than no button. `listening` reports that a transcription client is configured, not a live inference probe.
The launcher checks its local worker, and a failed recording request offers typing.
`speech.available` reports a loaded and warmed classroom voice. Hosted availability still
requires an actual request.

There is an eighth route the contract did not name: `GET /api/session/{id}/drawings/{drawing_id}`
returns the photograph, so the page can show a drawing it did not upload itself. It stops
answering when the live class ends. Persistent originals use the separately scoped `/api/courses` routes.

`options` per skill: `art-feedback` takes `{transcript?: string, rung?: 2|3}`;
`painting-to-animation` takes `{hint?: string}`, and `{media_kind: "figure"}` on it is read as
`painting-to-figure`, which takes no options and runs on the colour entrance only (the planner may
only ask for the animation skill, so the figure travels under its name); `drawings-to-storybook` uses 2–8 distinct selected drawings and previously confirmed transcripts;
it currently takes no generation options.
The lesson intent and the entrance are session settings, not options.

`transcript` is the child's own words and asks for beat four. The teacher types them, or the
child says them and `POST /heard` writes them down: that route transcribes one recording on the
box and returns text. By operator decision the chat's spoken answer is sent onward at
once, once the companion has opened the drawing; the teacher sees what was heard in the thread
before the reply and takes a misheard one back. Before the opening, and for a file or the
book's spoken ending, the page puts the text in the field for the teacher to confirm. Section 5a
wanted a person to see what was heard before anything used it. The recording is not stored, and 503 means no transcription model is running, which is not
fatal: typing always works. `rung` says
the child said nothing and asks for a smaller question; rung one is the opening question itself,
so only 2 and 3 exist. The two are exclusive and `rung` wins. Neither is meaningful on the first
request against a drawing: both follow an opening, and the harness writes one first if it is
missing. A drawing is screened once and the verdict is remembered, so a second request on the
same drawing reports no safety stage and a refused drawing stays refused.

`entrance` is the teacher's choice for the whole class, made by hand on the class sheet; the
page never detects it. On `colour` the child tells the story inside the picture and nothing is
ever corrected. On `sketch` the feedback reads light, proportion and structure and offers one
thing to try. It replaced the earlier per-session switch for a gentle suggestion.

## Events

Every `stage` event is one JSON object:

```json
{"stage": "art-feedback", "status": "running", "message": "Looking at the drawing",
 "ledger": {"ts": "...", "stage": "art-feedback", "gate": null, "tokens": 0, "wall_s": 0.0,
            "mem_before_gb": 57.1, "mem_after_gb": 57.1}}
```

`status` is one of `running`, `gate_pass`, `gate_fail`, `repair`, `done`, `stopped`. A `done`
event carries `outputs`. A `stopped` event carries a `message` the child may hear and a
`reason_code` that only the ledger view shows (`blank_page`, `photo_not_drawing`, `unsafe_image`,
`model_unavailable`, `not_built`, `rubric_failed`). The page never shows a reason code to a child.

**A stopped request also sends a `done` event carrying the same object.** The page ends a request
on `done` and reads a stream that merely closes as a model outage, so without it a kind refusal
arrives wearing "Splat needs a little rest".

**Art feedback shows its words while the rules judge them** (operator). Between the
writing and the rubric gate, an `art-feedback` request sends a `running` event carrying
`partial: {"text": ..., "question": ..., "checking": true, "revised": bool}` — the redacted words, not
yet passed, split into observation and closing question exactly as `done` will split them. The page
shows them labelled as a draft under review, replaces them with each newer draft and with the `done`
result, and never speaks them; only `done` outputs are read aloud.

**Text streams while it is written** (operator). While the model of an `art-feedback`,
`teacher-review`, `scene-description` or `story-outline` request writes, the request sends `running`
events carrying `partial: {"text": ..., "writing": true, "revised": bool}` (plus `"question"` for
`art-feedback`), at most every 0.15 s and once more when the call ends (`studio/core/harness.py`,
`WRITING_EVERY_S`). Each carries the whole text of the current call so far, never a piece, so a newer
one replaces an older one; a retry or a hand-over to another model starts again from nothing.
`revised` is true once that request's check has sent a draft back. A `story-outline` is written as JSON
and its partial `text` is the passages found so far, blank-line separated. The words are redacted like
the final text, are not checked, and are never spoken. Only the StepFun and llama/vLLM providers
stream (`studio/server/textstream.py`); any other provider sends no `writing` events, and the page waits for
`done` as before. The page places the words where the checked ones will stay: the partner's turn and
the ask-the-child card, the teacher review panel, the planner (`studio/page/src/29g-text-stream.js`).

**A reply to a child starts with a bridge** (operator). Before the reply is written, an
`art-feedback` request that carries the child's words sends a `running` event with
`partial: {"bridge": ..., "written": true|false}`: the child's words said back plus a fixed "let me look
again", from the fast `chat.bridge` model, or the fixed line from `studio/conversation/strings.json` when that model
fails or its echo does not pass the instant checks (`studio/conversation/bridge.py`). The page shows it as the
partner's turn and speaks it at once; the `done` reply is spoken after it ends, and not at all if the
teacher has moved to another drawing. The bridge never describes the drawing and is not saved to the course.

**A rejected draft is a `stopped` event with more on it.** When the independent review of a scene
description or story outline says no, the `stopped` (and `done`) object also carries
`review_failed: true`, the `candidate` the teacher may edit, and `issues`: a list of
`{"evidence", "suggestion"}` pairs in the reviewer's words, shown beside the draft. The ledger line
for that gate keeps only the verdict sentence, never the issues: the reviewer compares the candidate
with the child's words and the drawing, so its evidence describes both, and a ledger line holds
neither (added after a pull request that put the evidence in the note was reviewed and
not merged).

**The stream also carries SSE comment lines**, which `EventSource` ignores by specification: `: open`
as soon as the response starts, and `: keep-alive` whenever the request has been silent for
`KEEP_ALIVE_S` seconds (2, in `studio/serve.py`), because a video stage can sit for minutes with no
transition to report. A reader that is not `EventSource` must skip lines starting with `:`.

## Outputs

| Skill | `outputs` |
|---|---|
| `art-feedback` | `{text, question, language, beat, rubric: {passed: boolean, failed: [int]}}` |
| `sketch-to-3d` | `{scene, language}` — perspective geometry for the local relighting viewer |
| `painting-to-animation` | `{keyframe: {kind: "keyframe", image, width, height}, language}` — generated still PNG via image.edit |
| `painting-to-figure` | `{figure: {version, parts: [{shape, at, size, turn, colour}]}, language, deployment}` — a toy of simple solids inspired by the painting, drawn by the isolated viewer at `/viewer/3d/figure.html`; held back as a `stopped` event with `figure_held_back` when it fails the check twice |
| `painting-to-scene` | `{preview_url, package_url}` |
| `drawings-to-storybook` | `{pages: [{drawing_id, text}], language}`; the page adds a child-authored ending, local reading and self-contained HTML export |

As first integrated, the user-selected FLUX.2 Klein 4B produces one **still keyframe**.
`image` is a normalized PNG data URI; output links and API credentials stay out of the response.
The page compares it with the original and exports PNG. This is not a video endpoint.
The input and generated image pass safety checks; pose fidelity remains teacher-reviewed.
Current profiles use Replicate, so this action is online. Failed jobs are not automatically
resubmitted; unchanged successful input reuses the conversation cache.

Legacy `choreography` responses remain readable by the old browser player. That format and
its bounds are documented in the [earlier motion report](../measured/local-animation-repair.md).
The classroom no longer asks a chat model for that plan.

`text` is two to four sentences; on the sketch entrance it carries the one thing to try. `question`
is the one open question the teacher asks the child: into the picture on colour, about the
child's own process on sketch. `beat` is `opening`, `reply`, `rung-2` or `rung-3`, and says which
of the four the page is showing. A reply usually has an empty `question`, which is what section 5a
asks for: once the child is talking, the machine stops asking.

## Ledger line

`{ts, request_id, stage, beat, inputs_hash, outputs_path, gate, tokens, cost, wall_s,
mem_before_gb, mem_after_gb, reason_code?, second_look?, note}`. `gate` is `pass`, `fail` or `null`
for stages without a gate. `beat` says which of the four the line belongs to.

`second_look` (added when the class began asking NVIDIA's safety model) is what that
second reader said about the drawing or the made picture: `clear`, `unavailable`, or the codes of
what it flagged, comma-separated (`violence,weapons`). Never its words. The ledger view shows the
codes and "not run" beside any refusal reason, and nothing for `clear`. `reason_code` is looked up
from the note's first word, because the second look's answer follows the verdict there.

Every number in a line is real, and at first none of them was: `tokens` counts what
the writer and its judges spent together, `mem_*` is read from the host, and `inputs_hash`
fingerprints the values rather than the field names — it took two distinct values across every
class ever run until it was fixed. `note` carries the gate's own verdict and never a description
of the drawing, and the whole class's lines are deleted when the class ends, because section 1a
promises nothing is kept.

## What the page promises

- It sends nothing anywhere except these routes on the same origin.
- It releases live working copies and audio when a class ends. The server's course Portfolio
  retains the originals, confirmed text and completed results across refreshes and server restarts.
- It renders every stage transition it receives, so a judge watching the page sees the same
  sequence the ledger records.
