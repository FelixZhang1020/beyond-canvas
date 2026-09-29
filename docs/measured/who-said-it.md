# A chat reply keeps the child's words with the character they meant

The operator: "fix the wrong character credited in chat replies". Seen in the castle class (彩画课堂 · 胡桃夹子)
while the showcase classes were filled: asked why the nutcracker soldier on the tower blew his trumpet, the
child said "to buy time", and the reply gave it to the mouse king; asked what that soldier would do next, the
child said "he runs down to shut the gate", and the reply gave it to the mouse soldiers.

**Why.** A child's he, she or it, or an answer that names no one, is about the one the companion's last
question asked about. The reply's writer had that question only as one line among the last ten turns, and
guessed: the loudest character in the story, or "you". The invention judge (rule 14) cannot see the
question, and "the mouse king" is no new content to it, so nothing refused those replies.

**What changed.**

- The reply prompt names the question the child is answering on its own line, and its rule 8 says whom the
  answer is then about (`skills/art-feedback/assets/prompts/colour-reply.txt`, `feedback.question_answered`).
- In colour classes, when the child's answer says he, she or it (not 他们, not the 他 of 其他 or 吉他), a judge
  reads the companion's whole last turn, the answer and the reply, beside the rubric's own judges, and a reply
  that gave the words to someone else is written again (`studio/prompts/who-said-it.txt`,
  `Gates._who_check`). The turn is `words.answered_turn`, the same one the writer is given; when that turn
  asked nothing, the judge is not asked. A judge that fails, answers something unreadable, or cannot tell,
  refuses nothing.

## Method

Both on the Spark's Qwen3.6 (`vlm.front` writes, `vlm.director` judges, profile `stepfun`), through
`test-on-spark.sh`, with scripts that printed and wrote nothing and were deleted afterwards.

- **Writer replay.** The castle drawing and its conversation read from the Portfolio (read-only), the two
  turns replayed eight times each through `feedback.write_reply`. The script counts a reply as wrong when its
  first sentence names a mouse character before the nutcracker soldier (or names only a mouse); it does not
  count "you", which only reading the replies finds.
- **Judge.** Labelled replies: the two seen in class, the writer's own wrong and right replies from the
  replay, and one right reply each from three other showcase drawings (fox, bear, cabin), each judged twice.

## Results

| What | Result |
|---|---|
| Writer, both turns, 16 replies, before | 6 of 16 gave the words to a mouse |
| Writer, question line and rule 8 (first wording) | 1 of 16 gave the words to a mouse |
| Writer, question line and rule 8 (narrowed, below) | 0 of 16 to a mouse; read by hand, 1 gave "to buy time" to "you" (你) |
| Judge, the question alone: wrong replies to "he runs down…" | 6 of 6 caught |
| Judge, the question alone: right replies | 26 of 26 passed |
| Judge, the whole turn: wrong replies to "he runs down…" | 6 of 6 caught |
| Judge, the whole turn: right replies (castle, fox, bear, cabin) | 14 of 14 passed |

The answer "to buy time" names no one and has no he or she, so the judge is never asked about it, and that
turn's ten replies were not sent to it. Its fix is the prompt's alone, which is why the writer replay matters
more than the judge's numbers.

**Narrowed rule 8** (code review): it applies only when the answer names no one else; "they" is out,
because a 他们 can be anyone; and "you" is right when the question asked about the child.

The opening benchmark (`evalkit.runner --profile stepfun --skill art-feedback --lang zh`) reads openings only
and does not reach this change; it read 89% before and 94% after, on different case counts, which is noise.

## What this does not show

The sample is small, from one class's two turns, and the same code varies from run to run
(docs/measured/overnight-2d-to-3d.md found 26–41 of 68 toys from one code). The judge was never shown a wrong reply to a
child's 她 or 它, only to 他. No real child's answer was measured: the showcase classes were written for the
showcase.
