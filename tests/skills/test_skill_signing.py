"""Every skill folder carries a signature that matches its bytes, and nothing more.

The catalog verifies a detached skill.oms.sig against the folder it ships with.
This suite verifies each of ours against the committed public key on every run,
so a folder edited after signing goes red here before it goes red there. And it
proves the check can fail three ways: a byte changed, a file added, and — the
case a code review raised — bytecode planted in a cache folder.
"""
import shutil
from pathlib import Path

import pytest

from evalkit import packaging, signing

SKILLS = Path("skills")


def clean_copy(tmp_path, name="art-feedback"):
    copy = tmp_path / name
    shutil.copytree(SKILLS / name, copy, ignore=shutil.ignore_patterns("__pycache__", "local"))
    return copy


def test_the_public_key_is_committed_and_the_private_key_is_not():
    assert signing.PUBLIC_KEY.is_file()
    assert ".studio" in signing.PRIVATE_KEY.parts, "the private key must live outside the repository"


@pytest.mark.parametrize("folder", [d.name for d in signing.skill_dirs(SKILLS)])
def test_every_skill_folder_verifies_in_the_form_git_ships(folder):
    signing.verify(SKILLS / folder, as_shipped=True)


def test_a_clean_copy_verifies_strictly_as_a_download_would(tmp_path):
    signing.verify(clean_copy(tmp_path))


def test_a_changed_byte_or_an_added_file_is_refused(tmp_path):
    copy = clean_copy(tmp_path)
    manifest = copy / "SKILL.md"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SKILL.md"):
        signing.verify(copy)
    manifest.write_text(manifest.read_text(encoding="utf-8")[:-1], encoding="utf-8")
    (copy / "extra.txt").write_text("x")
    with pytest.raises(ValueError, match="extra.txt"):
        signing.verify(copy)


def test_bytecode_planted_in_a_cache_folder_is_refused(tmp_path):
    """The first verifier excluded any __pycache__ it found in the folder under
    check, so a .pyc dropped beside a signed script verified fine and Python
    would have imported it. Exclusions are a fixed policy now, and a cache is
    an extra file like any other."""
    copy = clean_copy(tmp_path)
    cache = copy / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "feedback.cpython-313.pyc").write_bytes(b"\x00" * 16)
    with pytest.raises(ValueError, match="__pycache__"):
        signing.verify(copy)


def test_the_exclusion_policy_does_not_read_the_folder():
    assert signing.ignored() == [Path("skill.oms.sig")]


@pytest.mark.parametrize("folder", [d.name for d in signing.skill_dirs(SKILLS)])
def test_each_signature_records_only_the_fixed_policy(folder):
    """The library honours whatever exclusions a signature carries, so a
    signature made under a generous rule is generous everywhere. Ours carry
    the signature file plus the library's own four git names, which a shipped
    skill folder never contains — and _nothing_extra refuses them if it does.
    No cache folder, ever."""
    recorded = set(signing.recorded_ignores(SKILLS / folder / "skill.oms.sig"))
    assert recorded == {"skill.oms.sig", ".git", ".gitignore", ".gitattributes", ".github"}


def test_the_packaging_check_no_longer_has_a_missing_signature_to_report():
    for report in packaging.validate_all(SKILLS):
        assert report.warnings == [], report.render()
