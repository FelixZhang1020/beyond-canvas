# Hearing the child, on the box

Until now the teacher typed what the child said, which was
the honest fallback while nothing could listen. Something can now listen, and it
runs on the same machine as everything else.

## What runs

`whisper-server` from whisper.cpp, with `ggml-small-q5_1.bin` (190 MB), the
multilingual model rather than an English-only one:

```bash
whisper-server -m ~/.cache/whisper/ggml-small-q5_1.bin --port 7130 --convert
```

**`--convert` is no longer needed, and should not be used.** It shells out to
ffmpeg on every upload, and later that shell-out failed on every single
one — including a correctly formed 16 kHz mono WAV — which took the whole
listening path down and read as a model problem. The page now decodes what the
browser recorded and re-encodes it as 16 kHz mono WAV itself, which is the one
format every speech model reads without help. One less thing to install on the
box, and one less thing to break during a class.

**And it was still in the launcher.** Found by sending real audio at
the running server: every request came back `500 FFmpeg conversion failed`, so
the listening path was down on this machine while the record above said the flag
should not be used. `studio/localmodels.sh` still passed it. A decision written
in a document and not carried into the script that starts the thing is a
decision that did not happen; `tests/test_transcribe.py` now reads the launcher
and fails if the flag comes back.

## What it does

| Spoken | Heard | Seconds |
|---|---|---:|
| "they are looking for his mum, she got lost a long time ago" | "They are looking for his mum. She got lost a long time ago." | 0.6 |
| a Chinese sentence about looking for a lost mother | the same sentence, verbatim | 0.2 |

Both verbatim, both faster than the page can animate. Transcription is not the
slow part of anything.

## The defect that would have been invisible

**Chinese came back in traditional characters.** The recording was in Mandarin
and the transcript read the right words in the wrong script.

That would not have looked like a bug. The teacher would read a correct
sentence, the skill would receive a correct sentence, and rule 13 — which checks
that the reply reuses the child's own words by overlapping character pairs —
would quietly match nothing, because the model replies in simplified. The reply
would be refused as not having heard the child, and the cause would be two
layers away from the symptom.

The fix is whisper's own initial prompt, in simplified characters. Same
recording, same model:

| Prompt | Transcript |
|---|---|
| none | traditional characters throughout |
| one simplified sentence | simplified characters throughout |

The prompt lives with the other Chinese strings in `studio/strings.json`, since
it is content rather than code, and a test holds that it is sent for Chinese and
not for English.

## What is deliberately not automatic

**The transcript is shown to the teacher before it is used.** Section 5a asks
for this in so many words: the child's words are transcribed first "so the
teacher can see what was heard and the transcript is auditable". The page fills
the field; a person still presses send. A machine that acted directly on what it
thought it heard would put a misheard sentence into a child's story with nobody
in a position to notice.

*Reversed for the chat (operator: a press of Send after every
recording was one too many).* A spoken answer in the chat is now sent at once,
once the companion has opened the drawing. The teacher still sees what was heard,
in the thread before the reply, and takes a misheard answer back before it reaches
a story; the book's spoken ending and a file still wait in their field, because a
misheard ending would become the child's last line in the book.

**Whisper's own annotations never reach a skill.** A silent room transcribes as
`[BLANK_AUDIO]`, and a reply built on that would answer a child who said nothing
at all. Those markers are stripped and an empty transcript reads as nothing
heard, which the page reports as "I could not make that out".

**Nothing is recorded to disk.** The audio is held in memory long enough to be
converted and transcribed, and then it is gone. Section 1a promises nothing is
kept, and a recording of a child is the most sensitive thing this product will
ever hold.

## What this does not settle

The spec wants Step-Audio 2 mini, the sponsor's own model, at about 3.2% error
on Chinese. This is not that model, and the comparison has not been run. What
this settles is that the loop no longer depends on a teacher typing, and that
the audio path is local — which was the part that could not be bought with a
hosted API, because no hosted transcription model on OpenRouter exists to buy.
