# Four faults in one class

Course `3f2328b0ef1e` (a 彩画课堂 course, colour entrance, zh) on the hosted Spark,
`https://{spark-address}:7100`. The operator reported four things; all four are read out of the
studio's own log (`~/logs/studio.log`) and the saved course (`.studio/portfolio.sqlite3`), not
inferred. Node time is CST throughout.

## What the record holds

Every activity saved for the drawing, in order:

| Node time | Skill | What it says |
|---|---|---|
| 13:27:06 | `teacher-review` | the teacher's own critique |
| 13:28:10 | `confirmed-words` | 你猜猜这只帕丁顿熊准备在大雪天去做什么？ |
| 13:30:03 | `art-feedback` (reply) | 帕丁顿熊在大雪天还提着箱子，他准备去做什么呢？ |
| 13:31:22 | `confirmed-words` | 他可能要去上学，风雪太大了，他的帽子都要被吹掉了。 |
| 13:31:47 | `art-feedback` (reply) | 你说他要去上学…他在走的时候会护着帽子吗？ |
| 13:32:18 | `confirmed-words` | 会的。 |

There is no `beat: opening` record. The conversation never opened.

## 1 · The words took a whole round to appear

The chat column is drawn only from the saved course (`26c-course-history.js` fetches
`/api/courses/<id>`), and it is redrawn on three occasions: the drawing changes, the class ends,
or a request finishes **successfully** (`30-main.js`, end of `onEvent`). Nothing draws the words
when they are sent. The gap is the model's: **113 s** for the first reply (13:28:10 → 13:30:03)
and **25 s** for the second.

## 2 · The third turn never appeared

`会的。` is in the course, saved at 13:32:18 — it was never lost. Its reply was never written,
so the column was never redrawn, so the words never reached the screen. The reply died at
**13:33:41**, when `POST /api/courses/3f2328b0ef1e/edit` arrived from another window:
`Classroom.edit_course` ends the course's existing editor, and `end()` sets `cancelled` on every
request that editor had running.

## 3 · A question was recorded as the child's answer

The page shows the composer whenever the chat tab has a drawing (`updatePrimary`:
`$('heard').hidden = !chatting`), and `04-components.css` hid `#buddy-actions` — the button that
asks the studio to open the conversation — **whenever the composer is visible**. On that tab
there was nothing to press and nothing to read: the only thing a teacher could do was type. The
teacher typed the question they wanted put to the child, and the studio, reached with a
transcript and no opening, quietly wrote an opening nobody ever saw (`Conversation._need_opening`)
and answered the question with a question.

## 4 · "服务器未接受任务" on the animation

Three POSTs, all 404: 13:45:04, 13:45:53, 13:46:10, all to `/api/session/3f2328b0ef1e/requests` —
the session ended at 13:33:41 by the second window. The page maps any HTTP error on submission to
`task.submission_failed`, which is why a class that had been taken over read as a server fault.
No video job ever started; nothing is known to be wrong with the clip itself.

Same fault, one window earlier: `POST /api/session/ee45f17d406c/requests` 404 at 13:44:12, the
editor opened at 13:10.

**Fixed separately and first**, in `d3c17d3` the same afternoon: the studio names that refusal
(`SessionGone`, code `session_gone`) and the page takes the course back itself, on the picture and
in the view the teacher was in, then asks for the last action once more. That covers every call
that belongs to a class — the request, a photograph, a recording, the studio speaking, a saved
draft, a settings change — so this document's account of the cause stands and the cure is there,
not here.

## Not part of the four, and worth knowing

The node's page sources were edited and `index.html` rebuilt **during the class** — 13:24, 13:25,
13:28, 13:29, 13:32, 13:34, 13:45, 13:46 — by another window working on layout, which also loaded
the class page with `?transport=mock` eleven times between 13:32 and 13:48 and opened courses in
the Portfolio. That is where the second editor at 13:33:41 came from. The page is served from disk
on every request, so a rebuild reaches the next reload of a live class.
