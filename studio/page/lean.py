"""Comments stay in the source and leave the page.

The fragments are written with prose comments, and every one of them used to go to every teacher: 48 KB
of whole-line comments in the script and 17 KB in the style, of a 608 KB page. This drops a script line only when
the whole line is a comment, never a line that carries code, and never a line inside a template literal (the relight
shader keeps its own comments in one); in the style it drops every /* */ comment and the blank lines left behind.

    python3 lean.py js  < script > page-script
    python3 lean.py css < style  > page-style

The style pass also writes out the page's named screen shapes. Which layout a screen gets — the stacked one
phones use, or the side-by-side one a laptop and an iPad use — is not a width alone: an iPhone on its side is wider
than the phone line but too short for anything beside anything. So the answer is written once, as
`@custom-media --stacked ...;` in the tokens, and every rule asks `@media(--stacked)`.
No browser reads @custom-media yet, so it is expanded here, alternative by alternative; a name nobody declared
stops the build rather than reaching the page as a query that matches nothing.
"""
import re
import sys

LINE_COMMENT = re.compile(r"^\s*//")
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
CUSTOM_MEDIA = re.compile(r"@custom-media\s+(--[\w-]+)\s+([^;]+);")
MEDIA = re.compile(r"@media\s*([^{]+)\{")
NAMED = re.compile(r"\(--[\w-]+\)")


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
    return "\n".join(line for line in screens(CSS_COMMENT.sub("", text)).splitlines() if line.strip()) + "\n"


def screens(text):
    """Write each `(--name)` in a media query out as the alternatives its @custom-media declares."""
    names = {name: [a.strip() for a in query.split(",")] for name, query in CUSTOM_MEDIA.findall(text)}

    def expand(match):
        if not NAMED.search(match.group(1)):
            return match.group(0)
        alternatives = []
        for alternative in match.group(1).split(","):
            alternative = alternative.strip()
            used = NAMED.findall(alternative)
            if len(used) > 1:
                raise SystemExit(f"one named screen per alternative: @media {match.group(1).strip()}")
            if not used:
                alternatives.append(alternative)
                continue
            if used[0][1:-1] not in names:
                raise SystemExit(f"no @custom-media declares {used[0]}: @media {match.group(1).strip()}")
            alternatives += [alternative.replace(used[0], each) for each in names[used[0][1:-1]]]
        return "@media " + ",".join(alternatives) + "{"

    return MEDIA.sub(expand, CUSTOM_MEDIA.sub("", text))


if __name__ == "__main__":
    sys.stdout.write({"js": script, "css": style}[sys.argv[1]](sys.stdin.read()))
