"""The page leaves its comments behind, and nothing else (studio/page/lean.py)."""
import importlib.util
import re
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("lean", Path("studio/page/lean.py"))
lean = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lean)


def test_a_whole_line_comment_leaves_and_a_line_with_code_stays_whole():
    source = "// why this exists\nconst a = 1;   // kept: the line has code\n  // an indented note\nconst url = 'https://x';\n"
    assert lean.script(source) == "const a = 1;   // kept: the line has code\nconst url = 'https://x';\n"


def test_a_comment_inside_a_template_literal_is_content_and_stays():
    source = "const shader = `\n  // a shader keeps its own comments\n  gl_FragColor = c;\n`;\n// gone\nrun();\n"
    assert lean.script(source) == "const shader = `\n  // a shader keeps its own comments\n  gl_FragColor = c;\n`;\nrun();\n"


def test_a_named_screen_is_written_out_as_each_alternative_it_declares():
    source = ("@custom-media --stacked (max-width:760px), (max-height:480px);\n"
              "@media(--stacked){.a{order:2}}\n"
              "@media (--stacked) and (orientation:landscape){.b{order:1}}\n"
              "@media(prefers-reduced-motion:reduce){.c{order:0}}\n")
    assert lean.style(source) == (
        "@media (max-width:760px),(max-height:480px){.a{order:2}}\n"
        "@media (max-width:760px) and (orientation:landscape),(max-height:480px) and (orientation:landscape){.b{order:1}}\n"
        "@media(prefers-reduced-motion:reduce){.c{order:0}}\n")


def test_a_screen_nobody_declared_stops_the_build():
    with pytest.raises(SystemExit, match="--stacked"):
        lean.style("@media(--stacked){.a{order:2}}\n")


def test_the_page_names_both_screens_and_every_breakpoint_uses_them():
    sources = sorted(Path("studio/page/src").glob("*.css"))
    page = lean.style("".join(path.read_text(encoding="utf-8") for path in sources))
    assert not re.search(r"@media[^{]*\(--", page) and "@custom-media" not in page
    raw = "".join(path.read_text(encoding="utf-8") for path in sources)
    assert "@media(max-width:760px)" not in raw.replace(" ", "") and "@media(min-width:761px)" not in raw.replace(" ", ""), \
        "a breakpoint chose the layout by width alone; it should ask (--stacked) or (--side-by-side)"


def test_the_style_leaves_its_comments_and_keeps_every_rule():
    source = "/* the tokens */\n:root{--a:1}\n.b{color:red} /* why red */\n/* two\n   lines */\n.c{margin:0}\n"
    assert lean.style(source) == ":root{--a:1}\n.b{color:red} \n.c{margin:0}\n"
