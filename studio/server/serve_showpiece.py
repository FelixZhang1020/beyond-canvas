"""The temple showpiece on the classroom's own port, built the first time it is asked for.

Beyond Canvas, the temple showpiece and the harness diagram are one system. They
were split across two ports because they grew in two places, and the
operator said so: "no need a dedicated port to run it". The Harness page
moved first because it is static; this is the other half, and the harder one,
because the showpiece needs a model driver and a 47 MB Blender file behind it.

Which is why none of that is built at startup. A teacher opening a class must not
pay for a demo they will never run: no model client, no STEPFUN_API_KEY, no GLB
export of a temple, no delay. The holder below builds all of it on the first
request to a `/showpiece` route and keeps it thereafter, and a classroom that
never sees one never builds anything.

The routes themselves are not written here. They live in
`studio/showpiece/routes.py` and the exhibit on 7090 serves the same ones from
the same code -- that port is unchanged, still the presenter script's link, and
still the fallback if anything here misbehaves.
"""

from __future__ import annotations

import threading
from pathlib import Path

from studio.showpiece.routes import PAGE, ShowpieceRoutes

# What the exhibit's own launcher uses, so both ways in show the same demonstration.
# `--quick` is on: a live run on this hardware renders small and short, or the
# temple answers in an hour instead of minutes.
MODEL = Path("output/foguang-east-hall/foguang-east-hall-v25.blend")
RUNS = Path(".studio") / "showpiece" / "runs"
# StepFun First, on the subscription; API First (per call) until it was archived. The showpiece has its
# own slot now: on vlm.studio it followed the class chat to Qwen, and a StepFun showcase runs on StepFun.
PROFILE, SLOT = "stepfun", "vlm.showpiece"
# A live run renders small (catalog.QUICK), and its pictures are judged on the same StepFun slot.
QUICK = {"slot": SLOT}


class ShowpieceHolder:
    """The driver, the page and the exported models, made once and then kept.

    The same three things the exhibit server holds as its own attributes; the
    handler reaches them through `_exhibit` and cannot tell which server it is
    running in. Built under a lock because the page opens several routes at once
    the moment it loads, and two threads racing would start two GLB exports of
    the same 47 MB file.
    """

    def __init__(self, model: Path = MODEL, runs: Path = RUNS, page: Path = PAGE) -> None:
        self.page = page
        self._model, self._runs = model, runs
        self._lock = threading.Lock()
        self._driver = None
        self.models_root = runs / "models"

    @property
    def driver(self):
        with self._lock:
            if self._driver is None:
                self._driver = self._build()
            return self._driver

    def _build(self):
        from studio.core.env import load_dotenv
        from studio.providers import build_client
        from studio.showpiece import catalog
        from studio.showpiece.driver import Driver
        from studio.showpiece.models import export_in_background
        from studio.core.slots import load_profile, resolve

        load_dotenv()
        config = resolve(SLOT, load_profile(PROFILE))
        config.options.setdefault("reasoning_effort", "low")
        model = self._model if self._model.is_file() else None
        driver = Driver(build_client(config), model, self._runs, cap=40,
                        agent_name=f"{config.model} via {config.provider}", quick={**catalog.QUICK, **QUICK})
        export_in_background(driver.model_path, self.models_root)
        return driver


class ShowpieceMount(ShowpieceRoutes):
    """The showpiece's routes, mounted on the classroom server under /showpiece.

    Only two things are added to what `ShowpieceRoutes` already does: where its
    driver and files are (`_exhibit`), and a redirect for the bare path, since
    the dashboard loads all of its scripts and its 3D library by relative name
    and they only resolve from `/showpiece/`.
    """

    @property
    def _exhibit(self) -> ShowpieceHolder:
        return self.server.showpiece

    def _showpiece_redirect(self) -> None:
        self.send_response(302)
        self.send_header("Location", "/showpiece/")
        self.send_header("Content-Length", "0")
        self.end_headers()
