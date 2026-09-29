# Signing the skills

NVIDIA's catalog wants every skill folder to ship a detached `skill.oms.sig` in the
OpenSSF Model Signing (OMS) format, so a person who downloads the folder can check
it is the one that was reviewed and signed. At first no skill here had one:
the design record's "model_signing with the team's key" named a key nobody had made.
Then the operator decided the key lives on the development Mac, and this file
records what was done so it can be repeated or moved.

## Where the key is

| Half | Path | In git? |
|---|---|---|
| Private key | `.studio/signing/beyond-canvas-skills.key` (mode 600, folder 700) | **Never.** `.studio/` is never committed |
| Public key | `skills/beyond-canvas-skills.pub` | Yes — anyone who clones can verify |

Made with `openssl ecparam -name prime256v1 -genkey -noout` (an ECDSA P-256 key,
the curve the library signs with) and `openssl ec -pubout` for the public half. The
public file is PEM inside but named `.pub`, not `.pem`: the development machine's
credential guard and the global gitignore both treat every `.pem` as a private key
and refuse to commit it, and a public key is the one file that has to be committed. If
the Mac is lost, the key is lost with it: make a new pair, commit the new public
key, and re-sign every folder. There is no recovery of a private key by design.

## Signing and verifying

One module decides what a signature covers, and the signer, the verifier, the
test and the command line all use it: [evalkit/signing.py](../../evalkit/signing.py).
The rule is fixed and short: **every file git ships in the folder, and nothing
else** — the signature file is the one exception, since it cannot hold its own
hash. A downloaded folder therefore verifies strictly: a file changed, a file
added, or a `__pycache__` with bytecode in it all fail. (The first version of
the module excluded any cache folder it found at verification time; code review
quickly pointed out that bytecode planted after signing would then verify,
which is the one thing a signature is for. Exclusions are policy now, never
discovered from the folder being checked, and the verifier walks the folder itself
and refuses any file the signature does not list — so a signature that carries a
generous exclusion list, from anywhere, is still refused here. The library records
its own four git names alongside; a shipped folder never holds them.)

On this machine the working tree carries caches and the gitignored
`evals/files/local`, so signing and the suite's own check use the *shipped form*:
a temporary copy of only the files git tracks — what a clone or a zip receives.

```bash
uv run python -m evalkit.signing sign skills/art-feedback   # needs the private key; rewrites skill.oms.sig
uv run python -m evalkit.signing sign skills                # every folder
uv run python -m evalkit.signing verify skills              # public key only; what a clone can do
```

`tests/skills/test_skill_signing.py` verifies every folder on every suite run and
proves the check can fail: a copy with one byte changed in `SKILL.md`, a copy with
one extra file, and a copy with a `.pyc` planted in `scripts/__pycache__` are all
refused with the path named. So **a folder edited
after signing turns the suite red until it is signed again** — which is the point.
Re-sign as the last step of any change to a skill folder, and commit the new
`skill.oms.sig` with it.

The library used is `model-signing` (a dev dependency; `uv sync` installs it). The
same signature verifies with the library's own command line, which is what the
catalog documentation shows:

```bash
.venv/bin/model_signing verify key <downloaded-folder> \
  --signature <downloaded-folder>/skill.oms.sig \
  --public_key beyond-canvas-skills.pub
```

Run against this working tree that command fails on the caches and the local
fixture folder, and it should: they are not part of the skill. Use
`uv run python -m evalkit.signing verify skills` here instead.

## What this does and does not prove

A signature proves the folder is unchanged since the holder of the private key
signed it. It does not prove who that holder is: a key pair carries no identity.
NVIDIA's own skills are signed with a certificate chained to an NVIDIA root, and
verified with `model_signing verify certificate`; a third party's skill verifies
against that third party's public key, which is what the command above does.
Whether the catalog accepts a key-pair signature or requires a certificate at
submission was not stated in the public documentation when this was written and
should be checked with the submission form.

## One structural change made for signing

`skills/painting-to-animation/evals/files` was a symlink to art-feedback's
fixtures. The signing library refuses symlinks by default (following one would
make the signature depend on a file outside the folder), and a symlink does not
survive a zip. The link was removed and the eval cases point at
`../art-feedback/evals/files/…` instead, the same way drawings-to-storybook's do.
