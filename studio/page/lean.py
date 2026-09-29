"""Comments stay in the source and leave the page.

The fragments are written with prose comments, and every one of them used to go to every teacher: 48 KB
of whole-line comments in the script and 17 KB in the style, of a 608 KB page. This drops a script line only when
the whole line is a comment, never a line that carries code, and never a line inside a template literal (the relight
shader keeps its own comments in one); in the style it drops every /* */ comment and the blank lines left behind.

    python3 lean.py js  < script > page-script
    python3 lean.py css < style  > page-style
"""
import re
import sys

LINE_COMMENT = re.compile(r"^\s*//")
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def script(text):
    kept, in_template = [], False
    for line in text.splitlines():
        comment = bool(LINE_COMMENT.match(line))
        if comment and not in_template:
            continue
        kept.append(line)
        if not comment and line.count("`") % 2:
            in_template = not in_template
    return "\n".join(kept) + "\n"


def style(text):
    return "\n".join(line for line in CSS_COMMENT.sub("", text).splitlines() if line.strip()) + "\n"


if __name__ == "__main__":
    sys.stdout.write({"js": script, "css": style}[sys.argv[1]](sys.stdin.read()))
