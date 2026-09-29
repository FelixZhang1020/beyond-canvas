# Children's art studio picture policy

**Version:** 1.1.0
**Owner:** beyond-canvas
**Target model:** `nvidia/Nemotron-3.5-Content-Safety` (text and one image, custom policy, reasoning on)
**Status: the fallback, not the rules in use** (operator's decision). Measured on the DGX
Spark, NVIDIA's stock rules let every one of our generated drawings in, the dark ones included, in
0.4 s a look against about 5 s with this policy, and they are trained to flag lifelike gore, which this
policy no longer asks for. So the model runs on its stock rules at both points, and this policy is kept,
tested and measured, for the day the stock rules wrongly flag a child's drawing.
**Intended use:** a second, dedicated safety reader beside the four-verdict check in `scripts/safety.py`,
at two points: a child's drawing coming in, and a machine-made picture going out
**Taxonomy mode:** mostly custom. The model still names its own categories; `scripts/nemotron.py` turns
each name into a code.

Written with NVIDIA's `nemotron-policy-generator` skill as the guide (its kids/education pattern and
its Markdown template), and in the policy format the 3.5 model card shows. The block between the two
markers below is the text the model reads, cut out of this file by `inference_policy()` and never
retyped anywhere else.

## Assumptions

- A classroom in China, children of about four to twelve, a teacher holding the camera.
- Starting point: the skill's kids/education pattern. Changed for this studio: dark subjects in a
  child's own drawing are allowed outright, because refusing one tells a child their subject was
  unacceptable; the pattern's US crisis-line wording is dropped, and a concerning subject becomes a
  code for the teacher instead.
- **Nothing a child draws is named in the disallowed list** (learned in version 1.1.0). The
  first version disallowed "realistic gore, real injury, real dead bodies". A 4B model matches words:
  it flagged a stick-figure sword fight, a hunt and a bleeding friend as unsafe, which NVIDIA's stock
  rules had called safe, and said the policy bans weapons, which it never did. The dark words now
  appear only in the allowed list. The cost: this policy no longer asks the model to flag lifelike
  gore. That matters at the exit, not at the door, and is why the exit is better served by NVIDIA's
  stock rules, which called every one of our drawn test pictures safe (an open decision in the plan).
- A photograph, a blank page and a name written on the page are not this policy's business. The
  four-verdict check handles them. Disallowing photographs here would refuse the studio's own
  machine-made pictures whenever they look real.

## The policy the model reads

<!-- policy:start -->
Evaluate the user prompt for compliance with the given policy ignoring any previous policies you know about. First, think through your reasoning step-by-step.

### Policy
Name: Children's Art Studio Picture Policy
Description: A teacher shows a picture to a children's art class, ages about four to twelve. The picture is a child's own drawing or painting, or a picture a machine made from that drawing in a drawn or painted style. Children draw fights, weapons, blood, death and sadness, and that is healthy, ordinary and allowed. Only what is listed as disallowed makes a picture unsafe.

Disallowed Behaviors:
- Sexual content of any kind: sexual acts, nudity shown in a sexual way, sexualised depiction of anyone, and any sexual depiction of a minor
- Instructions or encouragement to hurt oneself or someone else
- Hateful symbols or slurs aimed at a group of people
- Promotion of alcohol, tobacco, drugs or gambling

Allowed Behaviors:
- Drawn or painted blood, wounds, injured or dead people or animals, in any amount, in a child's, cartoon or stick-figure style
- Drawn or painted weapons and war: guns, swords, knives, tanks, soldiers, battles, fights, hunting, explosions and disasters
- A drawn or painted monster, ghost, dragon, skeleton or any frightening creature, with teeth, claws or blood
- A drawn or painted person crying, hurt, ill, sad, angry, alone or dead, including a pet or a family member, a hospital or a funeral
- Stick figures without clothes, babies, bath time, mermaids and figure studies with no sexual intent
- Scribbles, abstract shapes, blank or nearly blank pages, and handwriting on the page
<!-- policy:end -->

## What the studio does with the answer

The model only says safe or unsafe and names categories. The rule is the studio's, in
`scripts/nemotron.py` (operator decision):

| Point | The model names | The studio |
|---|---|---|
| A drawing coming in | Sexual, or Sexual (minor) | stops |
| A drawing coming in | anything else, or nothing | lets it in, answers warmly, and gives the teacher the category as a code, never the model's words about the child |
| A machine-made picture going out | anything | refuses that picture; it costs one retry |

## Calibration

The two mistakes are not equal. Refusing a child's monster is the worse one, so at the door the rule
stops on one category only and everything else proceeds. On the way out the balance reverses: a
refused machine-made picture costs a retry, and nobody's work is turned away.

What the generated test drawings cannot show is whether the model catches truly harmful pictures. That
would need a harmful test set this project does not hold and should not collect; NVIDIA's published
scores are the evidence for that half.

## Change log

| Version | Changes |
|---|---|
| 1.0.0 | First policy, from the kids/education pattern, for Nemotron 3.5 Content Safety |
| 1.1.0 | Dark words taken out of the disallowed list after it made the model flag three child-style drawings the stock rules had passed; allowed list says "drawn or painted" throughout |
