"""Explicit lazy media choices: never load or invoke a fallback implicitly."""
from copy import deepcopy
from studio.core.errors import ModelRefused
from studio.providers.media import MediaSlot


class LazyMediaClient:
    def __init__(self, config):
        self.config = deepcopy(config)
        self.model = config.model
        self._client = None

    def make(self, inputs):
        if self._client is None:
            from studio.providers import build_media_client
            self._client = build_media_client(self.config)
        return self._client.make(inputs)


class ClipChoices:
    """The class's two clip makers (operator): "spark", the 5-second Wan 2.2 clip on the Spark,
    and "online", the 5-second Wan 3.0 clip on DashScope.

    The Spark's can be closed to teachers (`spark_open=False`, from the profile): it holds about 72 GB of
    the node for eighteen minutes, and the operator closed it the day it opened. A closed maker is still named
    (`closed`) so the page can show it greyed, and a request for it is refused like an unknown one.
    """

    def __init__(self, spark, online, spark_open=True):
        self.clients = {"spark": spark, "online": online}
        self.makers = ("spark", "online") if spark_open else ("online",)
        self.closed = () if spark_open else ("spark",)
        self.model = getattr(spark, "model", "")

    def make(self, inputs):
        inputs = dict(inputs)
        maker = inputs.pop("clip_maker", None) or ("spark" if "spark" in self.makers else "online")
        if maker not in self.makers:
            raise ModelRefused("Unknown clip maker")
        return self.clients[maker].make(inputs)


def clip_makers(slot):
    """Which clip makers a class's clip slot offers: none without one, the Spark's alone unless both."""
    if slot is None:
        return []
    return list(getattr(getattr(slot, "client", None), "makers", None)
                or getattr(getattr(getattr(slot, "client", None), "inner", None), "makers", ("spark",)))


def closed_clip_makers(slot):
    """The clip makers the class names but does not let a teacher start (shown greyed on the page)."""
    client = getattr(slot, "client", None)
    return list(getattr(client, "closed", None) or getattr(getattr(client, "inner", None), "closed", ()))


def lazy_slot(config):
    return MediaSlot(LazyMediaClient(config), config.options['task'],
                     dict(config.options.get('fields', {})), dict(config.options.get('extra', {})),
                     tuple(config.options.get('array_fields', [])))


class MeshChoices:
    def __init__(self, configs):
        configs = list(configs)
        if not configs or len({c.model for c in configs}) != len(configs):
            raise ValueError("Mesh choices must have unique model IDs")
        self.slots = {c.model: lazy_slot(c) for c in configs}
        self.model = next(iter(self.slots))

    def make(self, inputs):
        choice = inputs.get('model_choice', self.model)
        if not isinstance(choice, str):
            raise ModelRefused('Unknown 3D model choice')
        if choice not in self.slots:
            raise ModelRefused('Unknown 3D model choice')
        return self.slots[choice].to_mesh(inputs.get('image'), subject=inputs.get('subject'), model_choice=choice)
