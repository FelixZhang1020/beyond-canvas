# The 3D figure's check, shown the card's picture instead of its own

**Why.** The figure card now draws the figure as the class page's viewer lights it (`studio/making/figure_card.py`).
The check that decides whether a figure reaches the child (`figure.look`, Step 3.7 Flash on `vlm.figure.look`) and
the safety screen on its way out still see the older flat picture (`figure_render.sheet`): dimmer colours, no
shadow, and painter's order that can paint a wall over what stands in front of it. The operator asked whether the
check judges differently when it sees the card's picture. **Nothing the class runs was changed to find out.**

**How.** `docs/measured/scripts/figure-check-picture.py`, on the Spark (main at 23e16ea), with the
class's own `stepfun` clients: `vlm.figure.look` (Step 3.7 Flash, reasoning medium, on the StepFun plan) and
`safety.image` with NVIDIA's reader, `point="out"`. Only the picture differs: **flat**, today's, or **card**, the
same two views (front, and turned 35°) in the same 960 × 360 sheet, drawn by `figure_card.picture`. Each figure was
judged 5 times with each picture, in shuffled order so neither picture ran at a better time; a class shows a
figure only when two looks in a row pass it, so "shown" below is the sum over figures of (passes ÷ 5)².

- **Saved:** the 21 figures in the Spark's Portfolio (9 classes), each of which passed the flat check twice when
  it was made.
- **Fresh:** one new figure from each of the same 21 paintings, by the class's `vlm.figure` writer, kept nowhere.

## Result

| Figures | Looks passed, flat | Looks passed, card | Shown of 21, flat | Shown of 21, card |
|---|---|---|---|---|
| Saved | 91 of 105 | 93 of 105 | 17.7 | 18.0 |
| Fresh | 90 of 105 | 96 of 105 | 16.7 | 18.6 |
| Both | 181 of 210 | 189 of 210 | 34.4 of 42 | 36.6 of 42 |

Per figure, the card's picture did better on 8, worse on 3 and the same on 31. A split of 8 to 3 comes from chance
alone about one time in four (two-sided sign test), so **this shows no harm, not a proven gain.**

| Figure | Flat | Card | What the check said when it failed |
|---|---|---|---|
| saved `4125f7e698a6` | 1/5 | 3/5 | arms and legs floating off the body (both pictures) |
| saved `7a790fa1039a` | 4/5 | 5/5 | flat, once: add the people with balloons and the church |
| saved `ff6af546b17f` | 0/5 | 1/5 | not the painting's fish (both) |
| saved `a96e735554c2` | 1/5 | 0/5 | not the painting's plants (both) |
| saved `78fdc69debb8` | 5/5 | 4/5 | card, once: add the Christmas tree in the archway |
| fresh `1680eceeffbd` | 4/5 | 5/5 | flat, once: make the building a log cabin with a porch |
| fresh `3522d9e14d9e` | 4/5 | 5/5 | flat, once: the small character should be a bear or dog |
| fresh `3885312b2c48` | 4/5 | 5/5 | flat, once: make it a fish |
| fresh `6c2fd87746dc` | 3/5 | 5/5 | flat: not the town scene; add eyes to the dog |
| fresh `5ed9bfa5c936` | 2/5 | 4/5 | a spotlight house; add eyes to the small figure (both) |
| fresh `367bd265b79f` | 4/5 | 3/5 | legs, a wing or foliage coming apart; add flamingos (both) |
| fresh `c86ad9e75936` | 4/5 | 4/5 | should be a fox, not a deer (both) |
| fresh `b9753d04cd9d` | 0/5 | 0/5 | a robot for a painting of plants (both, every time) |

The other 29 figures passed every look with both pictures.

**What the replies show.** The reasons are the same kind with either picture: mostly "not the painting's subject"
(22 fails flat, 19 card), then parts floating free (5 and 3), then missing eyes (4 and 2). The card's picture did
not wave through a figure of the wrong thing: the robot drawn for a painting of plants failed all ten looks. On the
dog of `6c2fd87746dc`, whose eyes the flat check twice called missing, the eyes are visible in both pictures, so the
lean is not explained by the flat picture hiding them.

**Safety screen.** Every figure passed with both pictures (42 of 42 each). The reader said "clear" every time; the
four-verdict screen called 14 flat and 12 card pictures "block" (not artwork), which does not hold back a toy the
studio drew itself (`Conversation.figure`).

**Speed.** A look took a median 11 s with either picture.

**Not measured.** Five looks per picture per figure cannot separate a difference this small from the check's own
variation: the same commit, run six times in one night, showed between 42% and 61% of its toys
([overnight-2d-to-3d.md](overnight-2d-to-3d.md)).
