# Asking every clip to move

**Question.** Some clips came back as the painting standing still for five seconds, when the
description from 聊聊你的画 only said what is in the picture. Does telling every clip to move fix it?

**What was tried.** Two changes to the clip's instruction in `studio/making/animation.py`: a sentence
after every description ("The clip moves clearly and continuously from the first frame to the last,
never a still picture: if the request above only describes the scene, bring everything painted in it
gently to life in its own natural way"), and a livelier default for a drawing with no description
("Every painted thing comes gently to life in its own natural way… figures move their bodies, and
whatever surrounds them sways, drifts, flows or twinkles") in place of "Whatever the child painted
stirs a little where it stands, and nothing else changes". The no-hands wording was untouched.

**How.** Three drawings from the node's Portfolio, one clip each with the old instruction and one
with the new, all six on the online clip maker (Wan 3.0, `video.online`), five frames of each laid
side by side.

| Drawing | Old instruction | New instruction |
|---|---|---|
| Nativity: castle, stable, robed figures, camels, night sky | nearly still | figures still nearly still; large new stars painted into the sky |
| Night pond with a firefly and a dragonfly | small movement | clearly more movement, both insects fly; the one real gain |
| Safari: jeep, zebras, leopard, giraffes on pale paper | the leopard walks | the jeep turned yellow, green grass and flowers painted over the paper |

No hands or brushes appeared in any of the six.

**Verdict: not adopted.** One drawing moved better; two gained things the child never painted, which
is the fault the whole instruction exists to prevent. "Bring everything painted to life" reads to the
model as permission to add and recolour. A next attempt should ask for movement of what is already
there and say, beside it, that nothing is added and no colour changes — and be tried on these same
three drawings before it ships. The change is not in the code.
