"""Generative media through Replicate's predictions API.

Replicate is the second media route, and it is here for what fal does not
serve. The one this product wants most is ShieldGemma 2: a real image safety
classifier with a tunable score, where today a general vision model stands in
and its threshold cannot actually be tuned. That slot is NOT wired into the
cloud profile — swapping the door every child's drawing passes through is a
decision about the product, not a consequence of adding a key.

Replicate can answer in the same connection. `Prefer: wait=n` holds the request
open for up to 60 seconds, which covers a safety verdict and most single
images, and anything slower falls back to polling. That is why a screening call
here costs one round trip rather than three.

Contract verified against replicate.com/docs/reference/http:
POST to `/v1/models/{owner}/{name}/predictions`, authenticate with `Bearer`,
statuses are starting, processing, succeeded, failed and canceled.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from studio.core.errors import ModelError, ModelRefused, ModelUnavailable
from studio.providers.media import MediaResult, urls_in

API_URL = "https://api.replicate.com/v1"
RETRYABLE = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

# The five states a prediction can be in, and the three that end it.
SUCCEEDED = "succeeded"
FINISHED = frozenset({SUCCEEDED, "failed", "canceled"})

# The longest `Prefer: wait` the API accepts. Asking for more is an error, not
# a longer wait, so this is a ceiling rather than a preference.
INLINE_WAIT_SECONDS = 60
POLL_SECONDS = 1.5
TIMEOUT_SECONDS = 300.0


class ReplicateClient:
    """One Replicate model, run as a prediction and waited for.

    The model name is `owner/name` as it appears in the URL of its page, for
    example `google-deepmind/shieldgemma-2-4b-it`.

    Community models use `/v1/predictions` with a version. Set `official: true`
    for Replicate official models: these use the stable owner/name endpoint
    directly, without inventing a pinned version from catalog metadata.
    Official endpoints are maintained by Replicate and are not weight-pinned.

    Community versions may be pinned in options; legacy unpinned experiments
    resolve the latest version once per client.
    """

    # The clock, as an attribute rather than a constructor argument: a poll loop
    # has to be testable without a test spending real seconds, and a sixth
    # parameter would put this constructor over the five the craft limits allow.
    _sleep = staticmethod(time.sleep)

    def __init__(
        self,
        model: str,
        options: dict[str, Any] | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("REPLICATE_API_KEY", "")
        if not key:
            raise ModelRefused(
                "REPLICATE_API_KEY is not set; get one at "
                "https://replicate.com/account/api-tokens and put it in .env. "
                "Replicate's own docs call this a token, but the name this "
                "project reads is REPLICATE_API_KEY."
            )
        self.model = model
        self.options = dict(options or {})
        if self.options.get("official") is True and self.options.get("version"):
            raise ModelRefused("Official models do not accept a pinned version configuration")
        self.timeout_s = float(self.options.get("timeout_s", TIMEOUT_SECONDS))
        self._headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": f"wait={INLINE_WAIT_SECONDS}",
        }
        self._client = client or httpx.Client(timeout=120.0)
        self._version_id: str | None = None

    def make(self, inputs: dict[str, Any]) -> MediaResult:
        """Run one prediction and return what it produced."""
        started = time.monotonic()
        url, body = self._where_to_post(inputs)
        payload = self._settle(self._call("POST", url, body), started)
        output = payload.get("output")
        metrics = payload.get("metrics") or {}
        estimate = float(self.options.get("price_usd", 0.0))
        for kind in ("input", "output"):
            estimate += (float(self.options.get(f"price_usd_per_{kind}_mp", 0.0))
                         * float(metrics.get(f"image_{kind}_megapixel_count") or 0.0))
        return MediaResult(
            urls=urls_in(output),
            payload=payload,
            price_usd=estimate,
            latency_s=time.monotonic() - started,
            provider="replicate",
            model=self.model,
        )

    def _where_to_post(self, inputs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """The prediction endpoint for this model, and the body it wants."""
        if self.options.get("official") is True:
            return f"{API_URL}/models/{self.model}/predictions", {"input": inputs}
        version = self._resolve_version()
        if version:
            return f"{API_URL}/predictions", {"version": version, "input": inputs}
        return f"{API_URL}/models/{self.model}/predictions", {"input": inputs}

    def _resolve_version(self) -> str:
        """This model's version, asked for once and remembered.

        Returns "" when the model publishes none, which sends the caller to the
        official-model endpoint instead. A lookup failure is not fatal here for
        the same reason: the other route may still work, and failing now would
        replace a usable error later with a confusing one now.
        """
        if self._version_id is None:
            pinned = str(self.options.get("version") or "")
            if pinned:
                self._version_id = pinned
            else:
                try:
                    found = self._call("GET", f"{API_URL}/models/{self.model}")
                except ModelError:
                    found = {}
                self._version_id = str((found.get("latest_version") or {}).get("id") or "")
        return self._version_id

    def _settle(self, payload: dict[str, Any], started: float) -> dict[str, Any]:
        """Wait for a terminal state, then insist it was a successful one.

        A prediction that failed still returns HTTP 200 with the reason in a
        field, so a client that only checked the status code would hand a
        caller an empty output and call it a success.
        """
        while payload.get("status") not in FINISHED:
            waited = time.monotonic() - started
            if waited > self.timeout_s:
                raise ModelUnavailable(
                    f"{self.model} was still {payload.get('status', 'unknown')} after "
                    f"{waited:.0f}s. Raise timeout_s in the slot options to wait longer."
                )
            self._sleep(POLL_SECONDS)
            payload = self._call("GET", self._where(payload))

        if payload.get("status") != SUCCEEDED:
            raise ModelRefused(
                f"{self.model} {payload.get('status')}: "
                f"{payload.get('error') or 'no reason given'}"
            )
        return payload

    def _where(self, payload: dict[str, Any]) -> str:
        """Where to read this prediction next."""
        url = (payload.get("urls") or {}).get("get") or ""
        if not url:
            raise ModelRefused(
                f"Replicate accepted the job for {self.model} but returned nowhere to "
                f"read it: {sorted(payload)}"
            )
        return url

    def _call(self, method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """One HTTP call, with Replicate's failures mapped onto the vocabulary."""
        try:
            response = self._client.request(method, url, headers=self._headers, json=body)
        except httpx.RequestError as error:
            raise ModelUnavailable(f"replicate unreachable: {error}") from error
        if response.status_code in RETRYABLE:
            raise ModelUnavailable(f"replicate {response.status_code}: {response.text[:200]}")
        if response.status_code == 402:
            raise ModelRefused(
                "Replicate has no credit on this account, so the model never ran. "
                "Add credit at https://replicate.com/account/billing — the key itself "
                "is fine, or this would have been a 401."
            )
        if response.status_code in (401, 403):
            raise ModelRefused(
                "Replicate rejected REPLICATE_API_KEY. Check the value in .env against "
                "https://replicate.com/account/api-tokens"
            )
        if response.status_code >= 400:
            raise ModelRefused(f"replicate {response.status_code}: {response.text[:200]}")
        try:
            return response.json()
        except ValueError as error:
            raise ModelRefused(f"replicate returned no JSON: {response.text[:200]}") from error
