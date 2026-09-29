"""Two requests on one drawing count their own spending (code review).

Since two lanes a drawing's conversation can serve a chat and a clip at the same time, and both use
its meters. The stage that finished first took the other request's tokens into its own ledger line.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

from studio.core.metering import MediaMeter, Meter, carried, counting_for, stop_counting
from studio.providers.base import ChatResult
from studio.providers.media import MediaResult


class Model:
    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        return ChatResult("ok", 10, 5, 0, 0.01, 0.0, "fake", "m")


class Clips:
    def make(self, inputs):
        return MediaResult(urls=[], content=b"clip", price_usd=0.5)


def spend_as(key, meter, calls, took, go):
    token = counting_for(key)
    try:
        for _ in range(calls):
            meter.chat("hi")
        go.wait()
        took[key] = meter.take()
    finally:
        stop_counting(token)


def test_each_request_takes_only_what_it_spent():
    meter, took, go = Meter(Model()), {}, threading.Barrier(2)
    threads = [threading.Thread(target=spend_as, args=(key, meter, calls, took, go))
               for key, calls in (("chat", 3), ("clip", 1))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert (took["chat"].calls, took["chat"].tokens) == (3, 45)
    assert (took["clip"].calls, took["clip"].tokens) == (1, 15)


def test_the_judges_on_their_own_threads_are_counted_for_the_request_that_asked():
    meter = Meter(Model())
    token = counting_for("chat")
    try:
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda call: call(), [carried(lambda: meter.chat("judge")) for _ in range(2)]))
        assert meter.take().calls == 2
    finally:
        stop_counting(token)
    assert meter.take().calls == 0, "nothing was left under no request"


def test_a_clip_is_counted_for_its_own_request():
    clips = MediaMeter(Clips())
    token = counting_for("clip")
    try:
        clips.make({})
    finally:
        stop_counting(token)
    assert clips.take().calls == 0, "another request takes nothing of the clip's"
    token = counting_for("clip")
    try:
        assert clips.take().cost_usd == 0.5
    finally:
        stop_counting(token)


def test_the_rubrics_own_judges_are_counted_for_the_request_that_ran_them():
    """Through run_rubric as a class runs it: its judges answer on a thread pool."""
    from evalkit.rubric import run_rubric

    class Judge(Model):
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            return ChatResult('{"grounded": ["a", "b"], "presumptive": [], "invented": []}', 10, 5, 0, 0.0, 0.0,
                              "fake", "m")

    judge = Meter(Judge())
    token = counting_for("chat")
    try:
        run_rubric("The dog is running to find his friend. Which way is the park?", entrance="colour",
                   image_data_uri="data:image/png;base64,iVBORw0KGgo=", client=judge,
                   child_said="the dog is running to find his friend in the park")
        assert judge.take().calls >= 2
    finally:
        stop_counting(token)
