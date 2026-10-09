# Renting the media slots

> **SUPERSEDED the same day it was written, in part.** The two HTTP contracts below are still
> accurate and still asserted by tests. Everything about *which vendor serves
> which slot* is not: the media slots moved from fal to Replicate, Kokoro was
> replaced by CosyVoice 2 for both voice slots, and slots are now addressed by
> task rather than by vendor field names. Three statements below are now false
> and are left in place rather than edited, because the reasoning that produced
> them is worth keeping: that `tts.studio` speaks English, that no endpoint
> exists for CosyVoice 2, and that four slots run on fal. Current state:
> `studio/profiles/cloud.yaml`.

Written when the decision was made to buy media keys rather than
wait for the Spark. This records the two HTTP contracts as they were actually
read, what was wired, and the three things that were deliberately left alone.

**What this does not contain is a measurement.** No live call has been made:
the keys were not yet in `.env` when this was written. Everything below is a
contract read from a vendor's documentation and a client tested against a mock.
The line that turns this file into a measured one is:

```bash
uv run pytest -m live -k "fal or replicate" -v
```

## The two contracts

Read when this was written, and each is asserted by a test so that a vendor changing it
shows up as a red test rather than as a runtime surprise.

| | fal | Replicate |
|---|---|---|
| Submit | `POST queue.fal.run/{model}` | `POST api.replicate.com/v1/models/{owner}/{name}/predictions` |
| Auth | `Authorization: Key <FAL_KEY>` | `Authorization: Bearer <REPLICATE_API_KEY>` |
| Waiting | poll `status_url` until `COMPLETED` | `Prefer: wait=60` answers inline, else poll `urls.get` |
| States | `IN_QUEUE`, `IN_PROGRESS`, `COMPLETED` | `starting`, `processing`, `succeeded`, `failed`, `canceled` |
| Source | fal.ai/docs/model-apis/model-endpoints/queue | replicate.com/docs/reference/http |

Two differences matter more than they look.

**fal is a queue and Replicate can answer inline.** A ShieldGemma verdict on
Replicate costs one round trip; the same work on fal would cost three. That is
why the safety slot, when it is wired, belongs on Replicate.

**Replicate returns HTTP 200 for a prediction that failed.** The reason sits in
a field, not in the status code, so a client that checked only the code would
hand its caller an empty output and call it success. `ReplicateClient` raises
instead, and `test_a_failed_prediction_is_an_error_and_not_an_empty_answer`
fails when that check is removed — verified by removing it.

## What was wired

Four slots in `studio/profiles/cloud.yaml`, all on fal: `image.edit`,
`tts.studio`, `video.scene`, `mesh.fast`. Nothing calls them yet. The three
skills that will — sketch-to-3d, painting-to-scene, drawings-to-storybook — are
gated to two later drops of the build plan, and the slots exist first so that the model is
already named, priced and reachable when a skill is written.

Prices are declared in the profile only where fal bills per call. Where fal
meters — per megapixel, per thousand characters — the field is absent and the
rate is in a comment, because a made-up per-call figure would be carried into a
cost report and believed. `MediaResult.price_usd` is named to say it is a list
price rather than a measurement; neither vendor reports cost in its response.

## Three things deliberately not wired

**`safety.image` on Replicate's ShieldGemma 2.** The real classifier is
available at about $0.001 a call and has the tunable score the current stand-in
lacks. It stays out for two reasons, and the second was discovered rather than
reasoned:

1. It is the door every child's drawing passes through. Swapping it is a
   decision about the product, not a consequence of buying a key.
2. **Adding it to the cloud profile would stop the studio page from starting.**
   `Classroom.__init__` builds a client for `safety.image` whenever the profile
   has one, and it calls `build_client`, which makes chat clients. A media
   provider there raises `UnknownProvider` before the page binds its port. So
   the swap is not a one-line profile edit; it needs the classroom to know
   which protocol the slot speaks.

**A Mandarin voice.** `tts.studio` points at `fal-ai/kokoro/american-english`,
which is the wrong language for this product and is marked as such in the
profile. It is the only Kokoro endpoint ID fal documents in full. fal's schema
names Mandarin voices — `zf_xiaobei`, `zm_yunjian` — but publishes no endpoint
ID for them, and a guessed ID would fail at the moment a child pressed play.
The page's own system voice already speaks Chinese for nothing.

**`mesh.premium` and `tts.export`.** Searching fal and Replicate found no
endpoint for Step1X-3D or CosyVoice 2 under those names. That is a search that
failed, not a proof that none exists.

## What this does not settle

Whether any of these models is good enough for a child's drawing. Nothing here
has produced a picture, a voice or a mesh — only the plumbing that would carry
one. The first honest number will come from the live tests above, and the first
useful one from a skill that a child's drawing actually passes through.
