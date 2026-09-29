# BENCHMARK: drawings-to-storybook

**Why there is no "with skill / without skill" table here, and no numbers either.** The model does
not make the book. The skill gathers drawings a class has already made, puts them in order, and
sets them beside words the child confirmed saying — it never writes words for a child. A bare model
given the same request would write a story, which is the one thing this skill exists not to do, so
a second row would compare two different products rather than measure one.

**This skill has not been measured on model quality, and nothing below pretends otherwise.** It is
the least measured of the six classroom skills. Saying so here is worth more than a number with
nothing behind it.

## What is actually held

| What | How |
|---|---|
| The book uses only drawings from the class's own portfolio | `tests/conversation/test_creation.py`, `tests/classroom/test_classroom_integration.py` — **17 tests** |
| The words are the child's confirmed words, never written for them | same |
| The skill package matches NVIDIA's format: SKILL.md, skill-card, evals, signature | `tests/skills/test_skill_packaging.py`, checked on every run |
| Five eval cases stating what a correct book is | `evals/evals.json` |

All of it runs on the Spark with the rest of the suite.

## What would measure it

The five eval cases are written and could be judged the way `evalkit/classbench.py` judges
`studio-safety` and `painting-to-animation` — each listed behaviour read against the result by a
judge model, with and without the skill. That needs a class whose portfolio already holds several
drawings and confirmed words, which no sample set provides today. It is not done, and it is the
obvious next measurement for this skill.
