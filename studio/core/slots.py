from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

PROFILE_DIR = Path(__file__).parents[1] / "profiles"


@dataclass(frozen=True)
class SlotConfig:
    """One slot resolved to the model that will serve it."""

    slot: str
    provider: str
    model: str
    options: dict[str, Any]


class UnknownSlot(KeyError):
    """The profile has no entry for the requested slot."""


def load_profile(name_or_path: str | Path) -> dict[str, SlotConfig]:
    """Read a profile. A bare name resolves inside the bundled profiles dir."""
    # A machine switch (BEYOND_CANVAS_MACHINE, `machine_profile`) sat here for a short while,
    # choosing stepfun-spark.yaml on the Spark; it went when the Mac + 4090
    # variant was archived and stepfun.yaml became the Spark's.
    slots, defaults = _read(name_or_path, frozenset())
    if not defaults:
        return slots
    return {
        name: replace(config, options={**defaults.get(config.provider, {}), **config.options})
        for name, config in slots.items()
    }


def _read(
    name_or_path: str | Path, seen: frozenset[Path]
) -> tuple[dict[str, SlotConfig], dict[str, dict[str, Any]]]:
    """Slots and per-provider defaults, before the two are put together.

    They are kept apart until the outermost call so that a child profile's
    `provider_options` can beat its parent's. Merged at each level instead, a
    parent's default would arrive here already wearing a slot's clothes, and a
    slot option always wins — so the child could never overrule its parent.
    """
    path = Path(name_or_path)
    if not path.suffix:
        path = PROFILE_DIR / f"{path}.yaml"
    if path.resolve() in seen:
        raise ValueError("Profile inheritance cycle")
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    slots, defaults = (
        _read(document["extends"], seen | {path.resolve()}) if document.get("extends") else ({}, {})
    )
    for provider, options in (document.get("provider_options") or {}).items():
        defaults[provider] = {**defaults.get(provider, {}), **(options or {})}
    slots.update({
        slot: SlotConfig(
            slot=slot,
            provider=entry["provider"],
            model=entry["model"],
            options=dict(entry.get("options") or {}),
        )
        for slot, entry in (document.get("slots") or {}).items()
    })
    return slots, defaults


def resolve(slot: str, profile: dict[str, SlotConfig]) -> SlotConfig:
    """Look up one slot, naming the alternatives when it is absent."""
    try:
        return profile[slot]
    except KeyError:
        raise UnknownSlot(
            f"slot {slot!r} is not in this profile; known slots: {sorted(profile)}"
        ) from None
