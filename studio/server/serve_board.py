"""The status board, the lights beside it, and the prompt page's wording.

Split out of `studio/serve.py` to bring that file back under the
500-line limit. These routes are the only ones that answer about the studio
itself rather than about a class or a course, which is what makes them a clean
piece to lift out whole.
"""

from __future__ import annotations

import datetime

from studio.core import prompt_book
from studio.ops.modelboard import page_html, read_board


class BoardRoutes:
    """The board page, the readiness lights and the prompt book, mixed into `StudioHandler`."""

    def _prompts(self) -> None:
        """Every instruction a model is given, read from where the studio reads it. Read only."""
        self._json(200, prompt_book.read())

    def _board(self) -> None:
        """The model board, served by the studio so it needs no second address.

        The standalone `studio.ops.modelboard` stays: a board served by the page
        cannot tell anyone the page is down, which is the one question worth
        asking when nothing is answering.
        """
        profile = self.server.classroom.profile
        port = self.server.server_address[1]
        self._bytes(200, page_html(profile, port).encode("utf-8"), "text/html; charset=utf-8")

    def _lights(self) -> None:
        """What the board page polls. Measured now, never cached."""
        lights = read_board(self.server.classroom.profile)
        from studio.ops.modelboard import Light
        voice = self.server.classroom.voice
        if voice is not None:
            lights = [light for light in lights if light.slot not in ("tts.studio", "tts.export")]
            for slot in ("tts.studio", "tts.export"):
                lights.append(Light(slot=slot, model=voice.model, url="", up=True,
                                    serving=voice.model, usage="课堂已接入",
                                    hosted=type(voice).__module__ == "studio.providers.stepfun_voice",
                                    purpose="课堂对话朗读。" if slot == "tts.studio" else "故事书与历史课程朗读；复用同一语音服务。",
                                    note="语音对象已初始化；不代表本轮合成成功，不单独计量模型内存。"))
        for light in lights:
            if light.slot == "studio.page":
                light.url = f"http://127.0.0.1:{self.server.server_address[1]}"
                light.up, light.note, light.serving = True, "", "Beyond Canvas"
                light.paths, light.disk_gb, light.ram_gb = [], None, None
                light.usage = "当前服务"
            elif light.slot in ("video.animation", "mesh.portrait"):
                attached = getattr(self.server.classroom, "editor" if light.slot == "video.animation" else "portrait")
                light.usage = "课堂已接入" if attached is not None else "课堂未启用"
        self._json(200, {
            "profile": self.server.classroom.profile,
            "at": datetime.datetime.now().strftime("%H:%M:%S"),
            "lights": [light.as_dict() for light in lights],
        })
