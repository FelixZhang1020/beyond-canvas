from __future__ import annotations

from studio.core.errors import UnknownProvider, UnknownTask
from studio.providers.base import ChatResult, VisionChatClient
from studio.providers.dashscopevideo import DashScopeVideoClient
from studio.providers.fal import FalClient
from studio.providers.llamacpp import LlamaCppClient
from studio.providers.localmesh import LocalMeshClient
from studio.providers.localvideo import LocalVideoClient
from studio.providers.localimage import LocalImageClient
from studio.providers.cloudmesh import CloudMeshClient
from studio.providers.hybridmesh import HybridMeshClient
from studio.providers.media import TASKS, MediaClient, MediaResult, MediaSlot
from studio.providers.openrouter import OpenRouterClient
from studio.providers.replicate import ReplicateClient
from studio.providers.safetyreader import SafetyReaderClient
from studio.providers.siliconflow import SiliconFlowClient
from studio.providers.stepfun import StepFunClient, StepFunMediaClient
from studio.core.slots import SlotConfig

__all__ = [
    "ChatResult",
    "MediaClient",
    "MediaResult",
    "MediaSlot",
    "VisionChatClient",
    "build_client",
    "build_media_client",
    "build_media_slot",
    "build_safety_reader",
    "key_for",
]

# Which environment variable each provider needs, in the one place that knows.
# A local server needs none, and "" says so rather than leaving the provider out
# and making an absent entry mean two different things.
KEYS = {
    "llamacpp": "",
    "localmesh": "",
    "localvideo": "",
    "localimage": "",
    "remotevoice": "",
    "safetyreader": "",
    "cloudmesh": "REPLICATE_API_KEY",  # Default choice; Pixal reads its fal key lazily.
    "hybridmesh": "",  # TRELLIS.2 is local; Pixal reads its fal key only when selected.
    "openrouter": "OPENROUTER_API_KEY",
    "fal": "FAL_KEY",
    "replicate": "REPLICATE_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
    "stepfun": "STEPFUN_API_KEY",
    "dashscopevideo": "DASHSCOPE_API_KEY",
}

# Providers that return files rather than sentences. They answer to a different
# protocol, so asking either builder for the other's provider is a mistake worth
# naming rather than a KeyError three frames later.
#
# `stepfun` is in NEITHER, on purpose: it is the only vendor here that sells both
# shapes, so which builder is right depends on the slot rather than on the
# provider name. The two builders below tell them apart by whether the slot
# declares a `task`, which is the same field `build_media_slot` already requires
# of every media slot — one discriminator, not a second list to keep in step.
MEDIA = frozenset({"dashscopevideo", "fal", "replicate", "siliconflow", "localmesh", "localvideo", "cloudmesh", "hybridmesh", "localimage"})
CHAT = frozenset({"openrouter", "llamacpp"})
# A dedicated safety model answers about one picture in fixed lines: a third protocol, with its own builder.
READERS = frozenset({"safetyreader"})
LOCAL = frozenset({"llamacpp", "localmesh", "localvideo", "hybridmesh", "localimage", "safetyreader"})


def is_disabled_stepfun_image_model(model: str) -> bool:
    """Identify StepFun image models without confusing Step1X-3D with Step1X-Edit."""
    name = model.lower()
    return name in {"step-2x-large", "step-image-edit-2", "step-1x-edit", "step1x"} or name.endswith("/step1x-edit")


def key_for(provider: str) -> str:
    """The environment variable this provider reads, or "" when it needs none."""
    return KEYS.get(provider, "")


def build_client(config: SlotConfig) -> VisionChatClient:
    """Turn one resolved slot into a chat client. The only place providers are named."""
    if config.provider == "openrouter":
        return OpenRouterClient(config.model, config.options)
    if config.provider == "llamacpp":
        return LlamaCppClient(config.model, config.options)
    if config.provider == "stepfun":
        if config.options.get("task"):
            raise UnknownProvider(
                f"slot {config.slot!r} declares task "
                f"{config.options['task']!r}, so it makes files rather than "
                "sentences; call build_media_client for it"
            )
        return StepFunClient(config.model, config.options)
    if config.provider in MEDIA:
        raise UnknownProvider(
            f"slot {config.slot!r} names {config.provider!r}, which makes files rather "
            "than sentences; call build_media_client for it"
        )
    if config.provider in READERS:
        raise UnknownProvider(
            f"slot {config.slot!r} names {config.provider!r}, a safety reader that answers "
            "about one picture; call build_safety_reader for it"
        )
    raise UnknownProvider(
        f"slot {config.slot!r} names provider {config.provider!r}, which has no client"
    )


def build_safety_reader(config: SlotConfig) -> SafetyReaderClient:
    """Turn one resolved slot into the safety skill's second reader."""
    if config.provider not in READERS:
        raise UnknownProvider(f"slot {config.slot!r} names {config.provider!r}, which is not a safety reader")
    return SafetyReaderClient(config.model, config.options)


def build_media_client(config: SlotConfig) -> MediaClient:
    """Turn one resolved slot into a media client: a job in, the files it made out."""
    if is_disabled_stepfun_image_model(config.model):
        raise UnknownProvider(f"StepFun image model {config.model!r} is disabled")
    if config.provider == "localimage":
        return LocalImageClient(config.model, config.options)
    if config.provider == "cloudmesh":
        return CloudMeshClient(config.model, config.options)
    if config.provider == "hybridmesh":
        return HybridMeshClient(config.model, config.options)
    if config.provider == "localmesh":
        return LocalMeshClient(config.model, config.options)
    if config.provider == "localvideo":
        return LocalVideoClient(config.model, config.options)
    if config.provider == "dashscopevideo":
        return DashScopeVideoClient(config.model, config.options)
    if config.provider == "fal":
        return FalClient(config.model, config.options)
    if config.provider == "replicate":
        return ReplicateClient(config.model, config.options)
    if config.provider == "siliconflow":
        return SiliconFlowClient(config.model, config.options)
    if config.provider == "stepfun":
        if not config.options.get("task"):
            raise UnknownProvider(
                f"slot {config.slot!r} names stepfun with no task, so it returns "
                "text; call build_client for it, or add `task: speak` if it was "
                "meant to be a voice"
            )
        return StepFunMediaClient(config.model, config.options)
    if config.provider in CHAT:
        raise UnknownProvider(
            f"slot {config.slot!r} names {config.provider!r}, which returns text; "
            "call build_client for it"
        )
    raise UnknownProvider(
        f"slot {config.slot!r} names provider {config.provider!r}, which has no client"
    )


def build_media_slot(config: SlotConfig) -> MediaSlot:
    """Turn one resolved slot into a media model addressed by what it does.

    The field map is validated here rather than at the moment of the call. A
    profile that maps a name the task does not have is a typo, and a typo that
    waits until a child is standing in front of the screen to announce itself
    has cost far more than one that refuses at startup.
    """
    task = str(config.options.get("task") or "")
    if task not in TASKS:
        raise UnknownTask(
            f"slot {config.slot!r} declares task {task!r}; "
            f"a media slot must name one of {sorted(TASKS)}"
        )
    fields = dict(config.options.get("fields") or {})
    unknown = sorted(set(fields) - set(TASKS[task]))
    if unknown:
        raise UnknownTask(
            f"slot {config.slot!r} maps {unknown}, which {task!r} does not take; "
            f"it takes {list(TASKS[task])}"
        )
    array_fields = config.options.get("array_fields", [])
    if not isinstance(array_fields, list) or any(
        not isinstance(name, str) or name not in TASKS[task] for name in array_fields
    ):
        raise UnknownTask(f"slot {config.slot!r} array_fields must list arguments of {task!r}")
    return MediaSlot(
        client=build_media_client(config),
        task=task,
        fields=fields,
        extra=dict(config.options.get("extra") or {}),
        array_fields=tuple(array_fields),
    )
