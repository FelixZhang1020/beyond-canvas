"""The page leaves its comments behind, and nothing else (studio/page/lean.py)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("lean", Path("studio/page/lean.py"))
lean = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lean)


def test_a_whole_line_comment_leaves_and_a_line_with_code_stays_whole():
    source = "// why this exists\nconst a = 1;   // kept: the line has code\n  // an indented note\nconst url = 'https://x';\n"
    assert lean.script(source) == "const a = 1;   // kept: the line has code\nconst url = 'https://x';\n"


def test_a_comment_inside_a_template_literal_is_content_and_stays():
    source = "const shader = `\n  // a shader keeps its own comments\n  gl_FragColor = c;\n`;\n// gone\nrun();\n"
    assert lean.script(source) == "const shader = `\n  // a shader keeps its own comments\n  gl_FragColor = c;\n`;\nrun();\n"


def test_the_style_leaves_its_comments_and_keeps_every_rule():
    source = "/* the tokens */\n:root{--a:1}\n.b{color:red} /* why red */\n/* two\n   lines */\n.c{margin:0}\n"
    assert lean.style(source) == ":root{--a:1}\n.b{color:red} \n.c{margin:0}\n"
