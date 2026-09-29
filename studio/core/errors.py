class ModelError(Exception):
    """Base for every model-call failure the studio recognises."""


class ModelUnavailable(ModelError):
    """Endpoint unreachable, rate limited, or out of credit. Worth retrying."""


class ModelRefused(ModelError):
    """Endpoint rejected the request. Retrying the same call will not help."""


class ModelCancelled(ModelRefused):
    """The teacher stopped the request between calls.

    A refusal, not an outage: the retry that exists for a flaky answer must not
    run the thing the teacher just stopped. Found by review, when
    a stopped teacher report raised the base error, was retried, and paid for a
    second full draft while the session stayed locked.
    """


class EmptyCompletion(ModelError):
    """The call succeeded but returned no text.

    Step 3.7 Flash spends its whole token budget on hidden reasoning when
    max_tokens is small and returns a null content field. Callers retry with a
    larger budget rather than treating the empty string as a valid answer.
    """


class UnknownProvider(ModelError):
    """A profile named a provider that no client implements."""


class UnknownTask(ModelError):
    """A media slot named a task no client knows how to shape a call for.

    Media models are addressed by what they do — speak, edit an image, make a
    mesh — so that swapping the model behind a slot is a profile edit. A slot
    with no task, or a task nobody serves, would silently fall back to passing
    a vendor's raw field names through skill code, which is the thing that
    design exists to prevent.
    """
