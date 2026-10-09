"""Sign a skill folder for the catalog, and verify one, by the same rule.

NVIDIA's catalog wants each skill to ship a detached `skill.oms.sig` in the
OpenSSF Model Signing format, covering every file in the folder. At first
nothing here could produce one: the design record's "model_signing
with the team's key" named a key nobody had made. The operator then decided
that the key lives on the development Mac, outside the repository, and that
the public half is committed so anyone who clones can check a folder is the
one that was signed.

What a signature covers is decided here and nowhere else, and it is a fixed
rule, not something read off the folder being checked: every file git ships
in the folder, and nothing else. The signature file is the one exception,
because it cannot contain its own hash. The first version of this module
discovered `__pycache__` folders at verification time and excluded whatever it
found, which meant bytecode planted after signing verified fine — the exact
thing a signature exists to catch (code review).

So a folder verifies strictly: anything extra, a cache included, fails it.
On this machine the working tree does carry caches and local fixtures, so
signing and the suite's own check use `shipped()` — a copy holding only the
files git tracks, which is what a clone or a zip receives.

Usage:
    uv run python -m evalkit.signing sign skills/art-feedback     needs the private key
    uv run python -m evalkit.signing verify skills                public key only
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from model_signing import hashing, signing, verifying

SIGNATURE = "skill.oms.sig"
ROOT = Path(__file__).resolve().parents[1]
# PEM content under a .pub name: the repository's credential guard and the global
# gitignore both treat *.pem as a private key, and a public key is the one thing
# that must be committed for anyone else to verify a folder.
PUBLIC_KEY = ROOT / "skills" / "beyond-canvas-skills.pub"
# Outside the repository on purpose; .studio/ is gitignored. Nothing reads this
# but `sign`, and nothing that clones the repository has it.
PRIVATE_KEY = ROOT / ".studio" / "signing" / "beyond-canvas-skills.key"


def ignored() -> list[Path]:
    """The fixed exclusion policy: the signature file, and nothing else.

    Deliberately takes no folder argument. An exclusion derived from what a
    folder happens to contain is an exclusion an attacker can add to.
    """
    return [Path(SIGNATURE)]


def _hashing() -> hashing.Config:
    return hashing.Config().set_ignored_paths(paths=ignored())


@contextmanager
def shipped(skill_dir: Path) -> Iterator[Path]:
    """A temporary copy of the folder holding only the files git tracks."""
    skill_dir = Path(skill_dir).resolve()
    listed = subprocess.run(["git", "ls-files", "-z", "--", str(skill_dir)], cwd=ROOT,
                            capture_output=True, check=True).stdout
    files = [ROOT / name for name in listed.decode().split("\0") if name]
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / skill_dir.name
        for source in files:
            target = copy / source.relative_to(skill_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        yield copy


def sign(skill_dir: Path, private_key: Path = PRIVATE_KEY) -> Path:
    """Sign the shipped form of the folder; write `skill.oms.sig` into the real one."""
    skill_dir = Path(skill_dir)
    signature = skill_dir / SIGNATURE
    with shipped(skill_dir) as copy:
        (signing.Config()
            .use_elliptic_key_signer(private_key=private_key)
            .set_hashing_config(_hashing())
            .sign(copy, signature))
    return signature


def verify(skill_dir: Path, public_key: Path = PUBLIC_KEY, *, as_shipped: bool = False) -> None:
    """Raise unless the folder is byte-for-byte what was signed, nothing added.

    Strict by default: this is what a person who downloaded the folder does.
    `as_shipped` checks the git-tracked form instead, for a working tree that
    carries caches and local fixtures of its own.
    """
    skill_dir = Path(skill_dir)
    if as_shipped:
        with shipped(skill_dir) as copy:
            _verify_strict(copy, public_key)
        return
    _verify_strict(skill_dir, public_key)


def _verify_strict(folder: Path, public_key: Path) -> None:
    signature = folder / SIGNATURE
    (verifying.Config()
        .use_elliptic_key_verifier(public_key=public_key)
        .set_hashing_config(_hashing())
        .verify(folder, signature))
    _nothing_extra(folder, signature)


def signed_files(signature: Path) -> set[str]:
    """The relative paths a signature vouches for, read from its signed statement."""
    bundle = json.loads(Path(signature).read_text(encoding="utf-8"))
    statement = json.loads(base64.b64decode(bundle["dsseEnvelope"]["payload"]))
    return {resource["name"] for resource in statement["predicate"]["resources"]}


def recorded_ignores(signature: Path) -> list[str]:
    """The exclusion list the signer baked into the signature.

    The library adds these to its own exclusions at verification time, so a
    signature made under a generous rule verifies generously wherever it goes.
    That is how the first signatures here let planted bytecode through: they
    carried the cache folders discovered at signing.
    """
    bundle = json.loads(Path(signature).read_text(encoding="utf-8"))
    statement = json.loads(base64.b64decode(bundle["dsseEnvelope"]["payload"]))
    return list(statement["predicate"].get("serialization", {}).get("ignore_paths", []))


def _nothing_extra(folder: Path, signature: Path) -> None:
    """Refuse any file the signature does not vouch for, whatever the library skipped."""
    present = {str(p.relative_to(folder).as_posix()) for p in folder.rglob("*") if p.is_file()}
    present.discard(SIGNATURE)
    extra = sorted(present - signed_files(signature))
    if extra:
        raise ValueError(f"Signature mismatch: files not covered by the signature: {', '.join(extra)}")


def skill_dirs(root: Path) -> list[Path]:
    return [child for child in sorted(Path(root).iterdir()) if child.is_dir()]


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if len(arguments) != 2 or arguments[0] not in ("sign", "verify"):
        print(__doc__.split("Usage:")[1].strip())
        return 2
    action, target = arguments
    root = Path(target)
    folders = skill_dirs(root) if root.name == "skills" else [root]
    failed = 0
    for folder in folders:
        try:
            if action == "sign":
                sign(folder)
                print(f"signed    {folder.name}")
            else:
                verify(folder, as_shipped=True)
                print(f"verified  {folder.name}  (shipped form)")
        except Exception as error:  # the library raises several kinds; all mean "not this folder"
            failed += 1
            print(f"FAILED    {folder.name}: {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
